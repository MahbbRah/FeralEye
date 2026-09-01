"""Diagnostic tool to test Google Drive authentication and upload."""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
import numpy as np
import cv2

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config
from cloud.gdrive_sync import GoogleDriveSync
from events.models import ConfirmedAlertEvent, FrameDetectionResult, Detection, BoundingBox


def test_gdrive(credentials_file: str, folder_id: str):
    print("=" * 60)
    print(" ☁️  Google Drive Cloud Sync Diagnostics")
    print("=" * 60)
    print(f"Credentials File : {credentials_file}")
    print(f"OAuth Configured : {'Yes' if config.GDRIVE_OAUTH_REFRESH_TOKEN else 'No'}")
    print(f"Target Folder ID : {folder_id or '(Root / None)'}")

    sync = GoogleDriveSync(
        service_account_json_path=credentials_file,
        oauth_client_id=config.GDRIVE_OAUTH_CLIENT_ID,
        oauth_client_secret=config.GDRIVE_OAUTH_CLIENT_SECRET,
        oauth_refresh_token=config.GDRIVE_OAUTH_REFRESH_TOKEN,
        folder_id=folder_id,
        enabled=True,
        upload_photos=True,
        upload_videos=True
    )

    print("\n1. Testing OAuth2 Token Acquisition...")
    token = sync._get_valid_token()
    if not token:
        print("❌ Failed to obtain OAuth2 token. Check your credentials in .env.")
        return False
    print("✅ Successfully authenticated with Google Drive API!")

    # Generate a dummy test image
    test_dir = Path("tests/test_evidence")
    test_dir.mkdir(parents=True, exist_ok=True)
    test_img_path = test_dir / f"gdrive_test_{int(datetime.now().timestamp())}.jpg"

    canvas = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(canvas, "FERALEYE GDRIVE TEST", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
    cv2.imwrite(str(test_img_path), canvas)

    print(f"\n2. Uploading test file: {test_img_path.name}...")
    file_id = sync.upload_file(test_img_path, subfolder_name="Test_Sync", mime_type="image/jpeg")
    if file_id:
        print(f"✅ Upload successful! Google Drive File ID: {file_id}")
        print("🎉 Google Drive Cloud Sync is 100% operational!")
        return True
    else:
        print("❌ File upload failed. Ensure the Google Drive folder is shared with the Service Account email.")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Google Drive sync credentials and upload")
    parser.add_argument("--credentials", type=str, default=config.GDRIVE_SERVICE_ACCOUNT_JSON or "./gdrive_credentials.json", help="Path to Service Account JSON key")
    parser.add_argument("--folder", type=str, default=config.GDRIVE_FOLDER_ID or "", help="Google Drive Folder ID")
    args = parser.parse_args()

    test_gdrive(args.credentials, args.folder)
