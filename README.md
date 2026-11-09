# Collage Studio

A local, offline-friendly **growing photo and video collage** for a projector, with optional **Google Drive folder synchronisation**. Photos appear one by one, stay on screen as the wall grows, and the composition resets when full. Works on Windows, macOS and Linux with Python 3.10+.

![Projector workflow](https://img.shields.io/badge/Projector-Fullscreen%20view-AD8BDD) ![Google Drive](https://img.shields.io/badge/Google%20Drive-Read--only%20sync-4EAB95)

**Privacy:** Your media is served locally on your computer. The app is configured to bind to `127.0.0.1`, not the wider internet. OAuth tokens never leave your computer for this app's own server (Google authentication itself uses Google's servers). Nothing is uploaded or modified in Drive.

## 1. Start the app (local photos first)

Download/unzip this project, then in a terminal **inside `CollageStudio`**:

```bash
python -m venv .venv
```

Activate:

- **Windows PowerShell:** `.venv\Scripts\Activate.ps1` (if PowerShell prohibits scripts, use `.venv\Scripts\python.exe` directly)
- **Windows CMD:** `.venv\Scripts\activate.bat`
- **macOS/Linux:** `source .venv/bin/activate`

Install dependencies and launch:

```bash
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:8000** in Chrome or Edge. Drop some `.jpg`, `.png`, `.webp`, `.gif`, `.bmp`, `.mp4`, `.webm`, `.mov` or `.m4v` files into `media/`, or enter the **full absolute path** to another local photo folder and click **Save**. It automatically rechecks the folder every 6 seconds; there is no need to restart.

**Quick launch later:** `start_windows.bat` on Windows, or `./start_mac_linux.sh` on macOS/Linux. These scripts create the venv/install on first run.

## 2. Google Drive setup (one time)

The app needs your permission to access your private Google Drive folder. Do not paste a password or OAuth token into ChatGPT or Codex.

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create or select a Google Cloud project.
2. Under **APIs & Services → Library**, **enable Google Drive API**.
3. Under **Google Auth Platform**, configure the OAuth consent screen (External is appropriate for personal Google accounts). While in **Testing** status, add *your Google email* under **Test users**. Google may change the navigation labels.
4. Under **Clients → Create Client**, choose application type **Desktop app**. Download the JSON credentials and save the file as **`CollageStudio/secrets/credentials.json`**.
5. On your own computer, run:

   ```bash
   python connect_drive.py
   ```

   A browser opens to Google's sign-in and consent. Authorise read-only access. The access and refresh tokens are stored in **`secrets/token.json`** locally. Never commit or share these files.
6. In Google Drive, open the folder you want to show, then copy its URL, e.g. `https://drive.google.com/drive/folders/YOUR_FOLDER_ID`.
7. Paste the URL into the **Google Drive folder URL** field in Collage Studio and press **Link**, then **Sync Google Drive now**. The app syncs automatically every ~45 seconds after that.

You can also enter just the folder ID. Only **direct children of the selected folder** are imported (not its subfolders). Media are downloaded into `cache/<folder-id>/` for smooth playback and temporary offline use. The app never deletes the Drive originals or its cached copies automatically; remove cached files yourself when appropriate.

**Important Google scope note:** The official read-only Drive scope is not technically limited to one folder. Google asks for broader *read-only Drive access*, although Collage Studio's code only lists/downloads the selected folder's direct media children. To avoid granting this scope, use Google Drive for Desktop and select the locally synchronised folder instead. Production/public distribution of an OAuth app using this scope may require Google app verification. For personal testing you may need to reauthorise when Google expires the test refresh token.

**Download limit:** videos larger than **300 MB per file** are skipped in v1 to avoid filling your laptop's disk. Google Docs/Sheets and unsupported file types are ignored. On transient network failures, already cached photos keep working.

## 3. Project it on a second screen

1. Plug your projector into your laptop (HDMI/USB-C) and set the laptop to **Extend display** (not Mirror), if you want separate controls.
2. Click **Open projector view** in the app. It opens a second tab/window with only the collage.
3. Move the new window to your projector's screen. Press **F11** (or click **Fullscreen** on the projector page).
4. Keep the controls on your laptop. Settings update in the projector window about every 7 seconds. The projector tab needs to stay open and your computer must remain awake.

Keyboard shortcuts (when not typing in a field): `Space` to pause/resume, `R` to restart, and `F` to toggle fullscreen inside projector mode.

## Behaviour and limitations

- Photos/videos accumulate progressively; after the chosen number of items, the wall briefly holds and fades out, then starts another random cycle.
- A newly detected file is prioritised for the next available spot while shuffling is enabled. A full collage is reset automatically; a collection with fewer images than its capacity loops those images after each cycle.
- Videos play silently by default. Enable their sound **in the projector window** after a user interaction to satisfy browser autoplay rules. Several videos may play at once; muting them is recommended for an event.
- Browser video codecs vary; for robust cross-platform playback use **MP4 (H.264 video / AAC audio)** or **WebM**. Not every `.mov` file can be played in the browser. `ffmpeg` can convert unsupported videos.
- Supports a single account and folder, no guest upload or public hosting; QR upload/moderation can be added as a future feature.
- Google Drive polling is periodic, not instant. Downloads take additional time, especially for long videos.
- The implementation is an MVP; performance depends on how many high-resolution photos/videos your laptop can render concurrently. Try a capacity of 12–22 and avoid 4K video loops on older laptops.

## Codex workflow

Open this repository/folder with Codex and ask it to improve features. `AGENTS.md` contains architecture, security constraints, and a prioritised enhancement list. Good starting prompt:

> Continue development of Collage Studio. Read AGENTS.md and README.md first. Keep the currently working, localhost-only projector presentation and Google Drive read-only folder sync. Improve the collage's layout to avoid overlap when space remains, add graceful handling for portrait/landscape images, and add an optional draggable QR-code upload feature with a private, moderator-approved queue. Preserve current APIs and add tests. Never commit OAuth credentials, cached Drive media, or private photos. Run all tests and summarise changes.

## Tests

```bash
pip install pytest httpx
python -m pytest -q
node --check static/app.js
```

## Technical notes

- `app.py`: FastAPI local HTTP server, media routing, persistent settings and background poller.
- `drive_sync.py`: Google Drive REST v3 read-only list/download and local cache manifest.
- `connect_drive.py`: Desktop-app OAuth consent through the user's browser.
- `static/`: vanilla HTML/CSS/JS UI; intentionally no frontend build tools to make first-time setup easy.
- `media/`: add local files here; `cache/`: downloaded Drive media. Both are `.gitignore`d.
- `secrets/`: Google credentials and tokens, excluded from git.
- `state.json`: persisted paths/settings, excluded from git.

## Sources

- [Google Drive Python API quickstart](https://developers.google.com/workspace/drive/api/quickstart/python)
- [Drive API files.list](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list)
- [Drive API downloading files](https://developers.google.com/workspace/drive/api/guides/manage-downloads)
