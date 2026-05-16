"""
Google Sheets Logger (BONUS)
Appends lead data to a Google Sheet as a live leads tracker
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SheetsLogger:
    def __init__(self):
        self.spreadsheet_id = os.getenv("GOOGLE_SHEET_ID", "")
        self.credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
        self._service = None

    def _get_service(self):
        """Lazy-load Google Sheets service"""
        if self._service:
            return self._service

        creds_file = Path(self.credentials_file)
        if not creds_file.exists():
            logger.warning(f"Google credentials file not found: {self.credentials_file}")
            return None

        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build

            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_file(str(creds_file), scopes=scopes)
            self._service = build("sheets", "v4", credentials=creds, cache_discovery=False)
            return self._service
        except Exception as e:
            logger.warning(f"Failed to initialize Google Sheets service: {e}")
            return None

    async def log(self, lead, status: str, pdf_path: Optional[str] = None):
        """Append lead row to Google Sheet"""
        if not self.spreadsheet_id:
            logger.info("[Sheets] GOOGLE_SHEET_ID not set — skipping sheets logging")
            return

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._append_row, lead, status, pdf_path)

    def _append_row(self, lead, status: str, pdf_path: Optional[str]):
        service = self._get_service()
        if not service:
            return

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        pdf_filename = Path(pdf_path).name if pdf_path else "N/A"

        row = [
            timestamp,
            lead.name,
            lead.email,
            lead.company,
            lead.role or "",
            lead.industry or "",
            lead.company_size or "",
            lead.website or "",
            lead.challenge or "",
            status,
            pdf_filename,
        ]

        try:
            # Ensure header row exists
            result = service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range="Sheet1!A1:A1",
            ).execute()

            if not result.get("values"):
                # Write headers first
                headers = [[
                    "Timestamp", "Name", "Email", "Company", "Role",
                    "Industry", "Company Size", "Website", "Challenge",
                    "Report Status", "PDF Filename"
                ]]
                service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range="Sheet1!A1",
                    valueInputOption="RAW",
                    body={"values": headers},
                ).execute()

            # Append data row
            service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range="Sheet1!A:K",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            ).execute()

            logger.info(f"[Sheets] Logged lead for {lead.company} (status: {status})")

        except Exception as e:
            logger.error(f"[Sheets] Failed to log: {e}")
