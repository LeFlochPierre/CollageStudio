"""Run once on YOUR computer. Opens Google consent in a local browser."""
from pathlib import Path
from drive_sync import SCOPES

ROOT = Path(__file__).resolve().parent
SECRETS = ROOT / "secrets"


def main():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise SystemExit("First run: pip install -r requirements.txt") from exc
    client = SECRETS / "credentials.json"
    if not client.exists():
        raise SystemExit("Missing secrets/credentials.json. Read README.md (Google setup).")
    flow = InstalledAppFlow.from_client_secrets_file(str(client), SCOPES)
    print("Opening Google in your browser. Authorise read-only access to Drive.")
    credentials = flow.run_local_server(port=0, open_browser=True)
    SECRETS.mkdir(exist_ok=True)
    token = SECRETS / "token.json"
    token.write_text(credentials.to_json(), encoding="utf-8")
    try:
        token.chmod(0o600)
    except OSError:
        pass
    print("Connected. Your credentials stay on your computer in secrets/token.json.")
    print("You can now run: python app.py")

if __name__ == "__main__":
    main()
