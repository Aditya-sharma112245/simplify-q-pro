"""
Google Drive Uploader (BONUS)
Archives generated PDFs to a Google Drive folder
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DriveUploader:
    def __init__(self):
        self.folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
        self.credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service

        creds_file = Path(self.credentials_file)
        if not creds_file.exists():
            return None

        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build

            scopes = ["https://www.googleapis.com/auth/drive.file"]
            creds = Credentials.from_service_account_file(str(creds_file), scopes=scopes)
            self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
            return self._service
        except Exception as e:
            logger.warning(f"Failed to init Drive service: {e}")
            return None

    async def upload(self, lead, pdf_path: Optional[str]):
        if not self.folder_id or not pdf_path:
            logger.info("[Drive] Folder ID not set or no PDF — skipping Drive upload")
            return

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._upload_file, lead, pdf_path)

    def _upload_file(self, lead, pdf_path: str):
        service = self._get_service()
        if not service:
            return

        try:
            from googleapiclient.http import MediaFileUpload

            file_name = Path(pdf_path).name
            file_metadata = {
                "name": file_name,
                "parents": [self.folder_id],
            }
            media = MediaFileUpload(pdf_path, mimetype="application/pdf")

            uploaded = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id,name,webViewLink",
            ).execute()

            logger.info(f"[Drive] Uploaded {file_name} → {uploaded.get('webViewLink', 'no link')}")

        except Exception as e:
            logger.error(f"[Drive] Upload failed: {e}")
