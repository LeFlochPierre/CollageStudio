"""Read-only Google Drive folder synchronisation. Nothing is uploaded or deleted."""
from __future__ import annotations

import json
import logging
import os
import re
from urllib.parse import urlparse
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
LOG = logging.getLogger(__name__)
MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".mp4", ".webm", ".mov", ".m4v"}
MAX_DOWNLOAD_BYTES = 300 * 1024 * 1024  # per file; protect the projector laptop disk


def ensure_credentials(secrets_dir: Path):
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise RuntimeError("Google libraries missing. Run: pip install -r requirements.txt") from exc

    token = secrets_dir / "token.json"
    if not token.exists():
        raise RuntimeError("Google Drive not authorised. Run: python connect_drive.py")
    creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token.write_text(creds.to_json(), encoding="utf-8")
        try:
            os.chmod(token, 0o600)
        except OSError:
            pass
    if not creds.valid:
        raise RuntimeError("Google authorisation has expired. Run: python connect_drive.py")
    return creds


def folder_id_from_url(raw: str) -> str:
    """Accept the Drive /folders/ URL or folder ID, never a general file URL."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    if '://' in raw:
        parsed = urlparse(raw)
        if parsed.scheme != 'https' or parsed.hostname != 'drive.google.com':
            raise ValueError('Use a Google Drive folder URL or a plain folder ID')
        match = re.fullmatch(r'/drive/(?:u/\d+/)?folders/([A-Za-z0-9_-]+)', parsed.path.rstrip('/'))
        if match is None:
            raise ValueError('Expected a Google Drive /folders/ URL')
        candidate = match.group(1)
    else:
        candidate = raw
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", candidate):
        raise ValueError("Enter a Google Drive folder ID or a URL like https://drive.google.com/drive/folders/...")
    return candidate


def sync_folder(folder_id: str, cache_dir: Path, secrets_dir: Path) -> dict:
    """List direct folder children, download changed supported files, retain cache offline."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    creds = ensure_credentials(secrets_dir)
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = cache_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        manifest = {}
    if not isinstance(manifest, dict):
        manifest = {}

    entries = []
    page_token = None
    while True:
        result = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken,files(id,name,mimeType,modifiedTime,size,capabilities(canDownload))",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        entries.extend(result.get("files", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    downloaded = 0
    skipped = 0
    for entry in entries:
        name = entry.get("name", "")
        suffix = Path(name).suffix.lower()
        mime = entry.get("mimeType", "")
        if suffix not in MEDIA_SUFFIXES or not (mime.startswith("image/") or mime.startswith("video/")):
            continue
        if entry.get("capabilities", {}).get("canDownload") is False:
            skipped += 1
            continue
        size = int(entry.get("size") or 0)
        if size > MAX_DOWNLOAD_BYTES:
            skipped += 1
            continue
        file_id = entry["id"]
        cache_name = f"drive_{file_id}{suffix}"
        dest = cache_dir / cache_name
        version = entry.get("modifiedTime", "")
        if dest.is_file() and manifest.get(file_id) == version:
            continue
        temp = cache_dir / (cache_name + ".part")
        try:
            req = service.files().get_media(fileId=file_id)
            with temp.open("wb") as fp:
                downloader = MediaIoBaseDownload(fp, req, chunksize=1024 * 1024)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                    if fp.tell() > MAX_DOWNLOAD_BYTES:
                        raise ValueError(f"File exceeds {MAX_DOWNLOAD_BYTES // 1024**2}MB download limit")
            temp.replace(dest)
            manifest[file_id] = version
            downloaded += 1
        except Exception as exc:
            temp.unlink(missing_ok=True)
            skipped += 1
            LOG.warning("Skipping Drive media %s: %s", name, exc)

    # Do not delete cache when a Drive item is removed; offline playing should continue.
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"files_seen": len(entries), "downloaded": downloaded, "skipped": skipped}
