"""
Run this script ONCE to generate token.json.
After that, the token is hardcoded and main.py uses it directly.

Steps:
1. Go to https://console.cloud.google.com/
2. Create a project → Enable Google Calendar API + Google Tasks API
3. Go to APIs & Services → Credentials → Create OAuth 2.0 Client ID (Desktop app)
4. Download the credentials JSON → save as backend/credentials.json
5. Run: python generate_token.py
6. A browser window will open → log in with the manager's Google account → allow access
7. token.json will be created in backend/
"""

"""
Run this script ONCE to generate token.json.
Works on GCP Cloud Workstation — no local browser needed.
"""

import json
from google_auth_oauthlib.flow import Flow

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

def main():
    flow = Flow.from_client_secrets_file(
        "credentials.json",
        scopes=SCOPES,
        redirect_uri="urn:ietf:wg:oauth:2.0:oob",  # Out-of-band — no localhost needed
    )

    auth_url, _ = flow.authorization_url(prompt="consent")

    print("\n" + "="*60)
    print("Open this URL in your local browser:")
    print("="*60)
    print(auth_url)
    print("="*60)
    print("\nAfter approving, Google will show you an authorization code.")

    code = input("\nPaste the authorization code here: ").strip()

    flow.fetch_token(code=code)
    creds = flow.credentials

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes),
    }

    with open("token.json", "w") as f:
        json.dump(token_data, f, indent=2)

    print("\n✅ token.json created successfully!")
    print("You can now run: uvicorn main:app --reload")

if __name__ == "__main__":
    main()