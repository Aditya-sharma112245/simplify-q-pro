"""
Lead Automation System - Main FastAPI Application
Automates lead intake → enrichment → PDF report → email delivery
"""

import os
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from pydantic import BaseModel, EmailStr
from typing import Optional

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/app.log")
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Lead Automation System", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Output dir
Path("outputs").mkdir(exist_ok=True)
Path("logs").mkdir(exist_ok=True)


class LeadSubmission(BaseModel):
    name: str
    email: str
    company: str
    website: Optional[str] = None
    role: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    challenge: Optional[str] = None
    phone: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/submit-lead")
async def submit_lead(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    email: str = Form(...),
    company: str = Form(...),
    website: str = Form(default=""),
    role: str = Form(default=""),
    industry: str = Form(default=""),
    company_size: str = Form(default=""),
    challenge: str = Form(default=""),
    phone: str = Form(default=""),
):
    """Receive lead form submission and trigger automation pipeline"""
    lead = LeadSubmission(
        name=name,
        email=email,
        company=company,
        website=website or None,
        role=role or None,
        industry=industry or None,
        company_size=company_size or None,
        challenge=challenge or None,
        phone=phone or None,
    )
    
    logger.info(f"New lead received: {lead.name} from {lead.company} <{lead.email}>")
    
    # Fire-and-forget background pipeline
    background_tasks.add_task(run_pipeline, lead)
    
    return JSONResponse({
        "status": "success",
        "message": f"Thank you {lead.name}! We're preparing your personalized audit report. You'll receive it at {lead.email} shortly.",
    })


@app.post("/api/submit-lead")
async def submit_lead_api(lead: LeadSubmission, background_tasks: BackgroundTasks):
    """JSON API endpoint for lead submission"""
    logger.info(f"API lead: {lead.name} from {lead.company}")
    background_tasks.add_task(run_pipeline, lead)
    return {"status": "queued", "message": "Pipeline started"}


async def run_pipeline(lead: LeadSubmission):
    """Main automation pipeline"""
    from pipeline import LeadPipeline
    pipeline = LeadPipeline()
    await pipeline.run(lead)


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
