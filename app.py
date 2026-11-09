"""Collage Studio — local photo/video wall with optional read-only Drive sync."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from drive_sync import MEDIA_SUFFIXES, folder_id_from_url, sync_folder

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DEFAULT_LOCAL = ROOT / "media"
CACHE = ROOT / "cache"
SECRETS = ROOT / "secrets"
STATE = ROOT / "state.json"
VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".m4v"}
LOGGER = logging.getLogger("collage")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

state_lock = threading.RLock()
DEFAULT_CONFIG = {
    "local_folder": str(DEFAULT_LOCAL),
    "drive_folder": "",
    "interval": 5,
    "capacity": 150,
    "mix_videos": True,
    "shuffle": True,
    "video_sound": False,
    "drive_poll_seconds": 45,
}
config = DEFAULT_CONFIG.copy()
status = {"syncing": False, "last_sync": None, "last_result": None, "error": None}


def load_config():
    global config
    try:
        values = json.loads(STATE.read_text(encoding="utf-8"))
        if isinstance(values, dict):
            for key in DEFAULT_CONFIG:
                if key in values:
                    config[key] = values[key]
    except (FileNotFoundError, ValueError):
        pass


def save_config():
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2), encoding="utf-8")
    tmp.replace(STATE)


class ConfigPatch(BaseModel):
    local_folder: str | None = None
    drive_folder: str | None = None
    interval: int | None = Field(None, ge=1, le=30)
    capacity: int | None = Field(None, ge=3, le=150)
    mix_videos: bool | None = None
    shuffle: bool | None = None
    video_sound: bool | None = None


def list_media() -> tuple[list[dict], dict[str, Path]]:
    with state_lock:
        local = Path(config["local_folder"]).expanduser()
        drive_id = config["drive_folder"]
    sources = [("local", local)]
    if drive_id:
        sources.append(("drive", CACHE / drive_id))
    files = []
    paths: dict[str, Path] = {}
    for source, folder in sources:
        if not folder.is_dir():
            continue
        # .resolve() ensures symlinks cannot escape an approved source directory.
        root = folder.resolve()
        try:
            candidates = root.rglob("*") if source == "local" else root.glob("*")
            for p in candidates:
                if len(files) >= 10000:
                    break
                if p.suffix.lower() not in MEDIA_SUFFIXES or not p.is_file():
                    continue
                try:
                    relative = p.resolve().relative_to(root)
                    stats = p.stat()
                except (OSError, ValueError):
                    continue
                identifier = hashlib.sha256(f"{source}:{relative}".encode()).hexdigest()[:24]
                paths[identifier] = p
                files.append({
                    "id": identifier,
                    "name": p.name,
                    "kind": "video" if p.suffix.lower() in VIDEO_SUFFIXES else "image",
                    "source": source,
                    "url": f"/api/media/{identifier}",
                    "updated": int(stats.st_mtime),
                })
        except (OSError, PermissionError):
            LOGGER.warning("Cannot scan %s", folder)
    files.sort(key=lambda item: (-item["updated"], item["id"]))
    return files, paths


async def run_sync():
    with state_lock:
        if status["syncing"] or not config["drive_folder"]:
            return
        status["syncing"] = True
        folder = config["drive_folder"]
    try:
        result = await asyncio.to_thread(sync_folder, folder, CACHE / folder, SECRETS)
        with state_lock:
            status.update(last_sync=datetime.now(timezone.utc).isoformat(), last_result=result, error=None)
        LOGGER.info("Drive synchronised: %s", result)
    except Exception as exc:
        LOGGER.warning("Drive synchronisation failed: %s", exc)
        with state_lock:
            status["error"] = str(exc)
    finally:
        with state_lock:
            status["syncing"] = False


async def periodic_sync():
    await asyncio.sleep(2)
    while True:
        await run_sync()
        await asyncio.sleep(45)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_config()
    DEFAULT_LOCAL.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    task = asyncio.create_task(periodic_sync())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Collage Studio", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/display", response_class=HTMLResponse)
def display():
    return (STATIC / "display.html").read_text(encoding="utf-8")


@app.get("/static/{filename}")
def static(filename: str):
    if filename not in {"app.js", "style.css"}:
        raise HTTPException(404)
    return FileResponse(STATIC / filename)


@app.get("/api/config")
def get_config():
    with state_lock:
        return dict(config)


@app.patch("/api/config")
def patch_config(payload: ConfigPatch):
    changes = payload.model_dump(exclude_unset=True)
    if "drive_folder" in changes:
        try:
            changes["drive_folder"] = folder_id_from_url(changes["drive_folder"] or "")
        except ValueError as exc:
            raise HTTPException(422, detail=str(exc)) from exc
    if "local_folder" in changes:
        raw = (changes["local_folder"] or "").strip()
        folder = Path(raw).expanduser() if raw else DEFAULT_LOCAL
        if not folder.is_dir():
            raise HTTPException(422, detail="Local folder must be an existing directory")
        changes["local_folder"] = str(folder.resolve())
    with state_lock:
        if "drive_folder" in changes and changes["drive_folder"] != config["drive_folder"]:
            status.update(last_sync=None, last_result=None, error=None)
        config.update(changes)
        save_config()
        return dict(config)


@app.get("/api/media")
def media_list():
    files, _ = list_media()
    return {"items": files, "total": len(files)}


@app.get("/api/media/{identifier}")
def media_file(identifier: str):
    _, paths = list_media()
    path = paths.get(identifier)
    if path is None:
        raise HTTPException(404, detail="Media not found")
    return FileResponse(path)


@app.get("/api/status")
def get_status():
    with state_lock:
        return {**status, "drive_connected": (SECRETS / "token.json").exists(), "drive_folder_set": bool(config["drive_folder"])}


@app.post("/api/sync")
async def sync_now():
    await run_sync()
    return get_status()


if __name__ == "__main__":
    import uvicorn
    print("\nCollage Studio: http://127.0.0.1:8000\nProjector:      http://127.0.0.1:8000/display\n")
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8000")))
