"""Interactive OAuth2 Token Generator for Personal Google Drive accounts."""

import os
import sys
import json
import urllib.parse
from pathlib import Path
import requests

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
SCOPES = "https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/drive"


def main():
    print("=" * 65)
    print(" ☁️  Google Drive User OAuth2 Token Setup")
    print("=" * 65)
    print("\nGoogle Service Accounts have 0 bytes storage for personal @gmail.com accounts.")
    print("Using a User OAuth2 Refresh Token allows FeralEye to use your personal 15GB+ Drive quota!\n")

    client_id = config.GDRIVE_OAUTH_CLIENT_ID or input("Enter your Google OAuth Client ID: ").strip()
    client_secret = config.GDRIVE_OAUTH_CLIENT_SECRET or input("Enter your Google OAuth Client Secret: ").strip()

    if not client_id or not client_secret:
        print("\n❌ Error: Client ID and Client Secret are required.")
        return

    # Build auth URL
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("\n👉 Step 1: Open this link in your web browser:")
    print("-" * 65)
    print(url)
    print("-" * 65)
    print("\n👉 Step 2: Sign in with your Google Account, click 'Allow', and copy the authorization code.\n")

    auth_code = input("Paste the Authorization Code here: ").strip()
    if not auth_code:
        print("❌ Authorization code is empty.")
        return

    print("\nExchanging authorization code for permanent Refresh Token...")
    res = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
        timeout=15.0
    )

    if res.status_code == 200:
        data = res.json()
        refresh_token = data.get("refresh_token")
        print("\n🎉 SUCCESS! Your Google Drive User OAuth is ready.")
        print("=" * 65)
        print("Copy and paste these 4 lines into your .env file:")
        print("=" * 65)
        print(f"GDRIVE_SYNC_ENABLED=true")
        print(f"GDRIVE_OAUTH_CLIENT_ID={client_id}")
        print(f"GDRIVE_OAUTH_CLIENT_SECRET={client_secret}")
        print(f"GDRIVE_OAUTH_REFRESH_TOKEN={refresh_token}")
        print("=" * 65)
    else:
        print(f"❌ Failed to exchange token ({res.status_code}): {res.text}")


if __name__ == "__main__":
    main()
