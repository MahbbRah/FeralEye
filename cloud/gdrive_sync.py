"""Google Drive Cloud Sync Provider for Photos and 20s Video Clips."""

import os
import json
import time
import base64
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any
import requests

from events.models import ConfirmedAlertEvent

logger = logging.getLogger("camera_guard.cloud.gdrive")


class GoogleDriveSync:
    """
    Uploads evidence photos and 20s video clips to Google Drive.
    
    Supports:
    - User OAuth2 Credentials (Recommended for personal @gmail.com accounts)
    - Google Cloud Service Account JSON file (for Google Workspace Shared Drives)
    """

    TOKEN_URL = "https://oauth2.googleapis.com/token"
    DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true"
    DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
    SCOPES = "https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/drive"

    def __init__(
        self,
        service_account_json_path: Optional[str] = None,
        oauth_client_id: Optional[str] = None,
        oauth_client_secret: Optional[str] = None,
        oauth_refresh_token: Optional[str] = None,
        folder_id: Optional[str] = None,
        enabled: bool = False,
        upload_photos: bool = True,
        upload_videos: bool = True
    ):
        self.service_account_json_path = service_account_json_path
        self.oauth_client_id = oauth_client_id
        self.oauth_client_secret = oauth_client_secret
        self.oauth_refresh_token = oauth_refresh_token
        self.folder_id = folder_id.strip() if folder_id else None
        self.enabled = enabled
        self.upload_photos = upload_photos
        self.upload_videos = upload_videos

        self._access_token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._folder_cache: Dict[str, str] = {}
        self._lock = threading.Lock()

        if self.enabled:
            logger.info(
                f"☁️ [Google Drive Sync] ENABLED. Creds: '{self.service_account_json_path}', "
                f"Folder ID: '{self.folder_id or '(Root)'}'"
            )
        else:
            logger.info("☁️ [Google Drive Sync] DISABLED in config (GDRIVE_SYNC_ENABLED=false).")

    def sync_event_async(self, event: ConfirmedAlertEvent) -> None:
        """Queues background upload of event photo and/or video."""
        if not self.enabled:
            logger.debug("Google Drive sync skipped: GDRIVE_SYNC_ENABLED is false.")
            return

        logger.info(f"☁️ [Google Drive] Queuing upload for Event ID: {event.event_id}...")
        thread = threading.Thread(
            target=self._sync_worker,
            args=(event,),
            name=f"GDriveSync-{event.event_id}",
            daemon=True
        )
        thread.start()

    def _sync_worker(self, event: ConfirmedAlertEvent) -> None:
        """Worker thread executing photo and video uploads."""
        date_folder_name = event.triggered_at.strftime("%Y-%m-%d")
        logger.info(f"☁️ [Google Drive] Starting background sync worker for Event {event.event_id} (Target folder: '{date_folder_name}')...")

        # 1. Upload Evidence Photo
        if self.upload_photos and event.evidence_image_path:
            img_path = Path(event.evidence_image_path)
            if img_path.exists():
                logger.info(f"☁️ [Google Drive] Uploading photo: {img_path.name}...")
                file_id = self.upload_file(img_path, subfolder_name=date_folder_name, mime_type="image/jpeg")
                if file_id:
                    logger.info(f"✅ ☁️ [Google Drive] Photo uploaded successfully! File ID: {file_id}")
            else:
                logger.warning(f"Google Drive: Evidence image not found on disk: {img_path}")

        # 2. Upload Evidence Video Clip
        if self.upload_videos and event.evidence_video_path:
            vid_path = Path(event.evidence_video_path)
            if vid_path.exists():
                logger.info(f"☁️ [Google Drive] Uploading 20s video clip: {vid_path.name} ({vid_path.stat().st_size} bytes)...")
                file_id = self.upload_file(vid_path, subfolder_name=date_folder_name, mime_type="video/mp4")
                if file_id:
                    logger.info(f"✅ ☁️ [Google Drive] 20s Event video uploaded successfully! File ID: {file_id}")
            else:
                logger.warning(f"Google Drive: Evidence video not found on disk: {vid_path}")

    def upload_file(
        self,
        file_path: Path,
        subfolder_name: Optional[str] = None,
        mime_type: str = "application/octet-stream"
    ) -> Optional[str]:
        """
        Uploads a single file to Google Drive.
        Returns the Google Drive File ID on success, or None on failure.
        """
        token = self._get_valid_token()
        if not token:
            logger.error("Google Drive upload aborted: No valid access token.")
            return None

        # Determine target parent folder
        parent_id = self.folder_id
        if subfolder_name and parent_id:
            parent_id = self._get_or_create_subfolder(subfolder_name, parent_id, token)

        try:
            metadata = {
                "name": file_path.name,
                "mimeType": mime_type,
            }
            if parent_id:
                metadata["parents"] = [parent_id]

            headers = {
                "Authorization": f"Bearer {token}",
            }

            files = {
                "data": ("metadata", json.dumps(metadata), "application/json; charset=UTF-8"),
                "file": (file_path.name, open(file_path, "rb"), mime_type)
            }

            response = requests.post(
                self.DRIVE_UPLOAD_URL,
                headers=headers,
                files=files,
                timeout=60.0
            )

            if response.status_code in (200, 201):
                res_data = response.json()
                return res_data.get("id")
            else:
                logger.error(f"Google Drive upload failed with status {response.status_code}: {response.text}")
                return None

        except Exception as e:
            logger.exception(f"Error uploading {file_path} to Google Drive: {e}")
            return None

    def _get_or_create_subfolder(self, folder_name: str, parent_id: str, token: str) -> str:
        """Finds or creates a date subfolder (e.g. 2026-09-01) inside parent folder."""
        cache_key = f"{parent_id}:{folder_name}"
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]

        headers = {"Authorization": f"Bearer {token}"}
        query = f"name = '{folder_name}' and '{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"

        try:
            # Check existing
            res = requests.get(
                self.DRIVE_FILES_URL,
                headers=headers,
                params={"q": query, "fields": "files(id, name)"},
                timeout=10.0
            )
            if res.status_code == 200:
                files = res.json().get("files", [])
                if files:
                    folder_id = files[0]["id"]
                    self._folder_cache[cache_key] = folder_id
                    return folder_id

            # Create folder
            meta = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id]
            }
            create_res = requests.post(
                self.DRIVE_FILES_URL,
                headers=headers,
                json=meta,
                timeout=10.0
            )
            if create_res.status_code in (200, 201):
                new_id = create_res.json().get("id")
                self._folder_cache[cache_key] = new_id
                return new_id

        except Exception as e:
            logger.error(f"Failed to query/create Google Drive subfolder '{folder_name}': {e}")

        return parent_id

    def _get_valid_token(self) -> Optional[str]:
        """Obtains or refreshes OAuth2 token using User OAuth or Service Account credentials."""
        with self._lock:
            if self._access_token and time.time() < (self._token_expiry - 60):
                return self._access_token

            # 1. Option A: Direct User OAuth2 Refresh Token (Uses your 5TB Google Drive personal quota)
            if self.oauth_refresh_token and self.oauth_client_id and self.oauth_client_secret:
                logger.info("🔑 [Google Drive] Authenticating via User OAuth2 Refresh Token (uses your personal Drive quota)...")
                try:
                    res = requests.post(
                        self.TOKEN_URL,
                        data={
                            "client_id": self.oauth_client_id,
                            "client_secret": self.oauth_client_secret,
                            "refresh_token": self.oauth_refresh_token,
                            "grant_type": "refresh_token"
                        },
                        timeout=10.0
                    )
                    if res.status_code == 200:
                        token_data = res.json()
                        self._access_token = token_data["access_token"]
                        self._token_expiry = time.time() + token_data.get("expires_in", 3600)
                        logger.info("✅ [Google Drive] User OAuth2 token refreshed successfully.")
                        return self._access_token
                    else:
                        logger.error(f"Google Drive User OAuth refresh failed: {res.status_code} - {res.text}")
                except Exception as e:
                    logger.error(f"Error refreshing Google Drive user OAuth token: {e}")

            # 2. Option B: Service Account JSON (Only works with Shared Drives / Google Workspace)
            logger.info("🔑 [Google Drive] Falling back to Service Account JSON...")
            if not self.service_account_json_path:
                logger.warning("Google Drive Sync: Missing GDRIVE_SERVICE_ACCOUNT_JSON or GDRIVE_REFRESH_TOKEN.")
                return None

            cred_path = Path(self.service_account_json_path)
            if not cred_path.exists():
                logger.error(f"Google Drive credential file not found at: {cred_path.resolve()}")
                return None

            try:
                # Try google-auth if installed
                try:
                    from google.oauth2 import service_account
                    import google.auth.transport.requests

                    creds = service_account.Credentials.from_service_account_file(
                        str(cred_path),
                        scopes=self.SCOPES.split()
                    )
                    request = google.auth.transport.requests.Request()
                    creds.refresh(request)
                    self._access_token = creds.token
                    self._token_expiry = time.time() + 3500
                    return self._access_token
                except ImportError:
                    pass

                # Pure Python Fallback (using standard cryptography / jwt if available)
                with open(cred_path, "r") as f:
                    sa_data = json.load(f)

                # Use cryptography to sign JWT without heavy Google SDKs
                from cryptography.hazmat.primitives import hashes
                from cryptography.hazmat.primitives.asymmetric import padding
                from cryptography.hazmat.primitives.serialization import load_pem_private_key

                now_ts = int(time.time())
                header = {"alg": "RS256", "typ": "JWT"}
                claim = {
                    "iss": sa_data["client_email"],
                    "scope": self.SCOPES,
                    "aud": sa_data.get("token_uri", self.TOKEN_URL),
                    "exp": now_ts + 3600,
                    "iat": now_ts
                }

                def _b64(d):
                    return base64.urlsafe_b64encode(json.dumps(d).encode("utf-8")).rstrip(b"=").decode("utf-8")

                unsigned = f"{_b64(header)}.{_b64(claim)}"
                private_key = load_pem_private_key(sa_data["private_key"].encode("utf-8"), password=None)
                signature = private_key.sign(unsigned.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
                jwt_token = f"{unsigned}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode('utf-8')}"

                res = requests.post(
                    sa_data.get("token_uri", self.TOKEN_URL),
                    data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": jwt_token},
                    timeout=10.0
                )
                if res.status_code == 200:
                    token_data = res.json()
                    self._access_token = token_data["access_token"]
                    self._token_expiry = time.time() + token_data.get("expires_in", 3600)
                    return self._access_token
                else:
                    logger.error(f"Failed to fetch Google OAuth token: {res.status_code} - {res.text}")
                    return None

            except Exception as e:
                logger.exception(f"Failed to authenticate with Google Drive service account: {e}")
                return None
