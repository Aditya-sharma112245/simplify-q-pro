# 🚀 Lead Automation System

> **Automated Lead Intake → Company Enrichment → Personalized PDF Report → Email Delivery**

A production-ready system that transforms a simple form submission into a fully researched, AI-generated business intelligence report — delivered to the prospect's inbox in minutes, with zero human intervention.

---

## 📐 Architecture Overview

```
Form Submission
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Application                          │
│  POST /submit-lead → validates → triggers background pipeline   │
└─────────────────────────┬───────────────────────────────────────┘
                          │  (async background task)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Lead Pipeline                                 │
│                                                                 │
│  1. CompanyEnricher ──────────────────────────────────────────  │
│     ├─ Scrape company website (httpx + BeautifulSoup)           │
│     ├─ DuckDuckGo search for LinkedIn signals                   │
│     ├─ DuckDuckGo news search for recent developments           │
│     └─ Claude Sonnet 4 synthesis → structured JSON insights     │
│                                                                 │
│  2. ReportGenerator ─────────────────────────────────────────   │
│     └─ ReportLab → professional multi-page PDF                  │
│        ├─ Cover page with company metadata                      │
│        ├─ Executive Summary + Key Insight                       │
│        ├─ Company Intelligence (facts grid, services)           │
│        ├─ 5-area Audit Findings with impact ratings             │
│        ├─ Pain Points vs Growth Opportunities (2-col)           │
│        ├─ Numbered Quick Wins                                   │
│        └─ CTA closing section                                   │
│                                                                 │
│  3. EmailSender ─────────────────────────────────────────────   │
│     └─ SMTP (Gmail/any) → HTML email + PDF attachment           │
│                                                                 │
│  4. SheetsLogger [BONUS] ────────────────────────────────────   │
│     └─ Google Sheets API → append lead row to tracker           │
│                                                                 │
│  5. DriveUploader [BONUS] ───────────────────────────────────   │
│     └─ Google Drive API → archive PDF to folder                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🗂️ Project Structure

```
lead-automation/
├── main.py               # FastAPI app — routes, form handler
├── pipeline.py           # Orchestrates the full workflow
├── enrichment.py         # Web scraping + Claude AI synthesis
├── report_generator.py   # ReportLab PDF builder
├── email_sender.py       # SMTP email with HTML body + PDF
├── sheets_logger.py      # [BONUS] Google Sheets logging
├── drive_uploader.py     # [BONUS] Google Drive archiving
├── templates/
│   └── index.html        # Lead intake form (full-page split design)
├── static/               # Static assets (CSS/JS if needed)
├── outputs/              # Generated PDFs saved here
├── logs/
│   └── app.log           # Application log
├── requirements.txt
├── .env.example          # Config template
└── README.md
```

---

## ⚡ Quick Start

### 1. Clone & Install

```bash
git clone <repo>
cd lead-automation
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ Yes | From [console.anthropic.com](https://console.anthropic.com) |
| `SMTP_HOST` | ✅ Yes | e.g. `smtp.gmail.com` |
| `SMTP_PORT` | ✅ Yes | `587` for TLS |
| `SMTP_USER` | ✅ Yes | Your email address |
| `SMTP_PASS` | ✅ Yes | Gmail App Password (not your login password) |
| `FROM_EMAIL` | ✅ Yes | Sender email |
| `GOOGLE_CREDENTIALS_FILE` | ⭐ Bonus | Path to GCP service account JSON |
| `GOOGLE_SHEET_ID` | ⭐ Bonus | Google Sheet ID for leads tracker |
| `GOOGLE_DRIVE_FOLDER_ID` | ⭐ Bonus | Drive folder ID for PDF archiving |

#### Gmail App Password Setup
1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Create an App Password for "Mail"
3. Use that 16-char password as `SMTP_PASS`

### 3. Run the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000) and submit a lead form!

---

## 🌟 Bonus Features Setup

### Google Sheets + Drive (Service Account)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable **Google Sheets API** and **Google Drive API**
3. Create a **Service Account** → Download JSON credentials
4. Save as `google_credentials.json` in project root
5. **Sheets**: Create a new Google Sheet → Share it with the service account email (`...@...iam.gserviceaccount.com`) as Editor → copy the Sheet ID from the URL
6. **Drive**: Create a Drive folder → Share with service account email → copy the folder ID from URL
7. Set in `.env`:
   ```
   GOOGLE_CREDENTIALS_FILE=google_credentials.json
   GOOGLE_SHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms
   GOOGLE_DRIVE_FOLDER_ID=1A2B3C4D5E6F...
   ```

---

## 🔄 Pipeline Flow Detail

### Step 1: Data Enrichment (`enrichment.py`)

The enricher runs **3 sources concurrently**:

- **Website Scraper**: Fetches the company's own website — extracts meta description, hero text, about section, listed services, and a body excerpt
- **LinkedIn/Web Search**: DuckDuckGo search for company size, team info, founding year
- **News Search**: Recent news and developments from the past year

All raw data is passed to **Claude Sonnet 4** which synthesizes it into a structured JSON with:
- Company overview, business model, target customers
- 5 detailed audit findings with impact ratings + recommendations
- Pain points and growth opportunities
- Quick wins, competitive landscape, personalized intro

**Fallback**: If any scraping source fails or Claude times out, graceful fallbacks ensure the pipeline continues with partial data.

### Step 2: PDF Generation (`report_generator.py`)

Built with **ReportLab** (no external dependencies / no browser required):

- **Cover Page**: Navy + electric blue design with company metadata cards
- **Header/Footer**: On every page via canvas callback
- **Executive Summary**: Personalized intro + key insight callout box
- **Company Intelligence**: 2-column fact grid + services list
- **Audit Findings**: Impact-colored cards (Red/Yellow/Green) with recommendations
- **Opportunities**: Side-by-side pain points vs growth table
- **Quick Wins**: Numbered action list with accent badges
- **CTA Closing**: Navy block with call-to-action

### Step 3: Email (`email_sender.py`)

Sends a **dual-part MIME email** (plain text + HTML):
- Branded dark-header HTML email
- Key insight callout, quick wins preview
- PDF attached as `CompanyName_Audit_Report.pdf`

---

## 🛡️ Error Handling & Resilience

| Failure Scenario | Handling |
|-----------------|---------|
| Website scraping blocked (403, timeout) | Gracefully skipped, Claude uses remaining data |
| All scraping fails | Claude synthesizes from form fields alone |
| Claude API error | Falls back to template-based enrichment |
| Email send fails | Logged, does not crash pipeline |
| Sheets/Drive API fails | Logged, pipeline continues |
| JSON parsing error | Fallback enrichment dict used |

---

## 🔌 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Lead intake form |
| `POST` | `/submit-lead` | Form submission (multipart) |
| `POST` | `/api/submit-lead` | JSON API submission |
| `GET` | `/health` | Health check |

---

## ⚙️ Assumptions & Tradeoffs

**Assumptions**:
- Company websites are publicly accessible (some block scrapers — handled gracefully)
- Prospect email is valid and reachable
- Claude Sonnet 4 has enough context from public data to generate meaningful insights

**Tradeoffs**:
- **ReportLab vs WeasyPrint**: ReportLab chosen for zero system dependency (no Chrome/Chromium). WeasyPrint produces more "web-like" PDFs but requires a browser engine.
- **DuckDuckGo vs paid APIs**: DuckDuckGo HTML scraping avoids API costs. For production, replace with SerpAPI, Clearbit, or Hunter.io for better reliability.
- **Synchronous PDF build**: ReportLab is CPU-bound — wrapped in `run_in_executor` to avoid blocking the event loop.
- **No database**: Leads logged to Google Sheets (BONUS) or log files. A production system should add PostgreSQL.

**Limitations**:
- Heavy JS-rendered sites won't be fully scraped (no headless browser)
- Very new companies may have minimal public data
- Email deliverability depends on SMTP reputation; consider SendGrid/Mailgun for production

---

## 📈 Production Recommendations

1. **Queue**: Replace `BackgroundTasks` with Celery + Redis for retries and monitoring
2. **Database**: Add PostgreSQL for lead storage and dedup
3. **Email**: Use SendGrid or AWS SES for deliverability + tracking
4. **Enrichment**: Add Clearbit, Hunter.io, or Apollo for professional-grade data
5. **Rate limiting**: Add API rate limiting to prevent abuse
6. **Auth**: Add API key auth if exposing the JSON endpoint
7. **Monitoring**: Add Sentry for error tracking
