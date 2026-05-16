"""
Lead Pipeline Orchestrator
Coordinates: enrichment → report generation → email → logging
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class LeadPipeline:
    def __init__(self):
        from enrichment import CompanyEnricher
        from report_generator import ReportGenerator
        from email_sender import EmailSender
        from sheets_logger import SheetsLogger
        from drive_uploader import DriveUploader

        self.enricher = CompanyEnricher()
        self.report_gen = ReportGenerator()
        self.email_sender = EmailSender()
        self.sheets_logger = SheetsLogger()
        self.drive_uploader = DriveUploader()

    async def run(self, lead):
        """Full pipeline: enrich → generate → email → log → archive"""
        start_time = datetime.utcnow()
        pdf_path = None
        report_status = "failed"

        try:
            logger.info(f"[PIPELINE] Starting for {lead.company} ({lead.email})")

            # Step 1: Enrich company data
            logger.info("[PIPELINE] Step 1: Enriching company data...")
            enriched_data = await self.enricher.enrich(lead)
            logger.info(f"[PIPELINE] Enrichment complete. Sources: {enriched_data.get('sources_used', [])}")

            # Step 2: Generate PDF report
            logger.info("[PIPELINE] Step 2: Generating PDF report...")
            pdf_path = await self.report_gen.generate(lead, enriched_data)
            logger.info(f"[PIPELINE] PDF generated: {pdf_path}")

            # Step 3: Send email with report
            logger.info("[PIPELINE] Step 3: Sending email...")
            await self.email_sender.send(lead, pdf_path, enriched_data)
            logger.info("[PIPELINE] Email sent successfully")

            report_status = "sent"

            # Step 4 (BONUS): Log to Google Sheets
            logger.info("[PIPELINE] Step 4: Logging to Google Sheets...")
            await self.sheets_logger.log(lead, report_status, pdf_path)

            # Step 5 (BONUS): Archive PDF to Google Drive
            logger.info("[PIPELINE] Step 5: Archiving to Google Drive...")
            await self.drive_uploader.upload(lead, pdf_path)

            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"[PIPELINE] ✅ Complete for {lead.company} in {elapsed:.1f}s")

        except Exception as e:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"[PIPELINE] ❌ Failed for {lead.company} after {elapsed:.1f}s: {e}", exc_info=True)

            # Still try to log failure
            try:
                await self.sheets_logger.log(lead, "failed", None)
            except Exception:
                pass

            # Send fallback email if PDF was generated
            if pdf_path and report_status != "sent":
                try:
                    await self.email_sender.send(lead, pdf_path, {})
                except Exception:
                    pass
