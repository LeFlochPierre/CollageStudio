# Collage Studio: development guide for Codex

This is a locally hosted, offline-friendly growing photo/video collage for dual-screen projector use.

## Architecture
- `app.py`: FastAPI app, local media scanning, safe file serving, JSON settings, Google Drive poller.
- `drive_sync.py`: authenticated read-only Drive listing and bounded cache downloading.
- `connect_drive.py`: interactive Google OAuth setup on the user's OWN computer.
- `static/`: dependency-free vanilla JS frontend, admin preview and projector-only display.
- `tests/`: backend invariants and API safety tests.

## Security/privacy constraints
- Never commit or print `secrets/credentials.json`, `secrets/token.json`, any OAuth token, or actual media.
- Bind server to `127.0.0.1` by default; do NOT expose to a public network without proper auth.
- Do not make the Google Drive folder public or request write permissions.
- A URL or folder ID alone does not grant access; OAuth is needed.
- Only allow media-type files served from the configured local folder or downloaded cache.
- Ensure Drive errors do not stop local-media playback.

## Product direction
- Growing collage only: add items continuously, leave previous items visible, clear at capacity, repeat.
- Images & MP4/WebM videos; videos muted initially for autoplay compatibility.
- Newly synced items should be prioritised in the next cycle.
- Display mode should contain no settings sidebar; the admin has one.
- Keep display aesthetically pleasing at 1920x1080 and 4K with low CPU usage.
- Preserve settings across reload and avoid image repeats within a cycle.
- Prefer testable, small modules; run `python -m pytest -q` and `node --check static/app.js` after changes.

## Good next enhancements
1. Photo EXIF handling & video thumbnails/transcoding of unsupported formats.
2. Optional QR-code guest uploads with moderator approval and authentication.
3. Live display settings sync across windows, better layout packing, fade animation presets.
4. Integration tests with a fake Google Drive service and resilience to network errors.
