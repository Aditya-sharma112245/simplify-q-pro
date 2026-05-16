"""
Email Sender Module
Sends personalized emails with PDF report attachment via SMTP or SendGrid
"""

import asyncio
import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class EmailSender:
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_pass = os.getenv("SMTP_PASS", "")
        self.from_name = os.getenv("FROM_NAME", "Intelligence Team")
        self.from_email = os.getenv("FROM_EMAIL", self.smtp_user)

    async def send(self, lead, pdf_path: str, enriched: dict):
        """Send email with PDF attachment"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_sync, lead, pdf_path, enriched)

    def _send_sync(self, lead, pdf_path: str, enriched: dict):
        if not self.smtp_user or not self.smtp_pass:
            logger.warning("Email credentials not configured — skipping email send")
            logger.info(f"[DRY RUN] Would send to {lead.email} with attachment {pdf_path}")
            return

        msg = MIMEMultipart("mixed")
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = lead.email
        msg["Subject"] = f"Your Personalized Business Audit Report — {lead.company}"

        # HTML email body
        html_body = self._build_html_email(lead, enriched)
        text_body = self._build_text_email(lead, enriched)

        alt_part = MIMEMultipart("alternative")
        alt_part.attach(MIMEText(text_body, "plain"))
        alt_part.attach(MIMEText(html_body, "html"))
        msg.attach(alt_part)

        # PDF attachment
        if pdf_path and Path(pdf_path).exists():
            with open(pdf_path, "rb") as f:
                pdf_data = f.read()
            attachment = MIMEApplication(pdf_data, _subtype="pdf")
            attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename=f"{lead.company}_Audit_Report.pdf",
            )
            msg.attach(attachment)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.from_email, lead.email, msg.as_string())
            logger.info(f"Email sent to {lead.email}")
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            raise

    def _build_html_email(self, lead, enriched: dict) -> str:
        headline = enriched.get("headline_insight", "")
        quick_wins = enriched.get("quick_wins", [])
        exec_summary = enriched.get("executive_summary", "")
        company_overview = enriched.get("company_overview", "")

        wins_html = ""
        for i, win in enumerate(quick_wins[:3]):
            wins_html += f"""
            <tr>
              <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0;">
                <span style="display:inline-block;background:#7C3AED;color:white;border-radius:50%;width:22px;height:22px;text-align:center;line-height:22px;font-weight:bold;margin-right:10px;">{i+1}</span>
                {win}
              </td>
            </tr>"""

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F8FAFF;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:30px 20px;">
      <table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;">
        
        <!-- Header -->
        <tr>
          <td style="background:#0D1B2A;border-radius:12px 12px 0 0;padding:32px 36px;">
            <div style="width:50px;height:4px;background:#2563EB;margin-bottom:16px;border-radius:2px;"></div>
            <h1 style="color:white;margin:0;font-size:26px;font-weight:700;">Your Business Audit Report</h1>
            <p style="color:#94A3B8;margin:8px 0 0;font-size:14px;">Prepared exclusively for {lead.company}</p>
          </td>
        </tr>
        
        <!-- Greeting -->
        <tr>
          <td style="background:white;padding:32px 36px;">
            <p style="color:#0D1B2A;font-size:16px;margin:0 0 16px;">Hi {lead.name},</p>
            <p style="color:#475569;font-size:14px;line-height:1.7;margin:0 0 20px;">
              We've completed your personalized Business Intelligence Audit for <strong>{lead.company}</strong>. 
              Based on our research, we've identified several strategic insights and actionable recommendations 
              specifically tailored to your context.
            </p>
            
            {"<div style='background:#EFF6FF;border-left:4px solid #2563EB;border-radius:4px;padding:16px 20px;margin:0 0 24px;'><p style='color:#1E40AF;font-weight:600;margin:0 0 6px;font-size:13px;'>💡 KEY INSIGHT</p><p style='color:#1E3A5F;font-size:14px;margin:0;line-height:1.6;'>" + headline + "</p></div>" if headline else ""}
            
            {"<p style='color:#475569;font-size:14px;line-height:1.7;margin:0 0 20px;'>" + exec_summary + "</p>" if exec_summary else ""}
          </td>
        </tr>
        
        <!-- Quick Wins -->
        {"<tr><td style='background:#F8FAFF;padding:24px 36px;border-top:1px solid #E2E8F0;'><h3 style='color:#0D1B2A;margin:0 0 16px;font-size:16px;'>🚀 Quick Wins We Identified</h3><table width='100%' cellpadding='0' cellspacing='0' style='background:white;border-radius:8px;border:1px solid #E2E8F0;'>" + wins_html + "</table></td></tr>" if quick_wins else ""}
        
        <!-- CTA -->
        <tr>
          <td style="background:#0D1B2A;padding:32px 36px;border-radius:0 0 12px 12px;text-align:center;">
            <p style="color:#CBD5E1;font-size:14px;margin:0 0 20px;line-height:1.6;">
              Your full audit report is attached to this email. We'd love to walk you through the findings and discuss a tailored strategy.
            </p>
            <a href="mailto:{self.from_email}?subject=Re: {lead.company} Audit Report" 
               style="display:inline-block;background:#2563EB;color:white;padding:14px 32px;border-radius:6px;font-weight:600;font-size:14px;text-decoration:none;">
              Reply to Schedule a Call →
            </a>
            <p style="color:#475569;font-size:12px;margin:20px 0 0;">
              {self.from_name} &nbsp;•&nbsp; Your Report is Attached as PDF
            </p>
          </td>
        </tr>
        
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    def _build_text_email(self, lead, enriched: dict) -> str:
        headline = enriched.get("headline_insight", "")
        quick_wins = enriched.get("quick_wins", [])

        wins_text = "\n".join([f"  {i+1}. {w}" for i, w in enumerate(quick_wins[:3])])

        return f"""Hi {lead.name},

We've completed your personalized Business Intelligence Audit for {lead.company}.

{f'KEY INSIGHT: {headline}' if headline else ''}

Your full audit report is attached to this email as a PDF.

QUICK WINS WE IDENTIFIED:
{wins_text}

We'd love to walk you through the findings. Just reply to this email to schedule a call.

Best regards,
{self.from_name}

---
Report prepared exclusively for {lead.company} ({lead.email})
"""
