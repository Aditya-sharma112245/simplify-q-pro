"""
PDF Report Generator
Creates a beautiful, professional, personalized audit report using ReportLab
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak, FrameBreak
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.colors import HexColor, white, black

logger = logging.getLogger(__name__)

# ── Brand Colors ──────────────────────────────────────────────────────────────
NAVY      = HexColor("#0D1B2A")
MIDNIGHT  = HexColor("#1B2A3D")
ELECTRIC  = HexColor("#2563EB")
CYAN      = HexColor("#06B6D4")
SLATE     = HexColor("#475569")
LIGHT_BG  = HexColor("#F8FAFF")
BORDER    = HexColor("#E2E8F0")
WHITE     = HexColor("#FFFFFF")
SUCCESS   = HexColor("#059669")
WARNING   = HexColor("#D97706")
DANGER    = HexColor("#DC2626")
ACCENT    = HexColor("#7C3AED")

IMPACT_COLORS = {"High": DANGER, "Medium": WARNING, "Low": SUCCESS}
IMPACT_BG     = {
    "High":   HexColor("#FEF2F2"),
    "Medium": HexColor("#FFFBEB"),
    "Low":    HexColor("#ECFDF5"),
}


class ColoredLine(Flowable):
    """A decorative colored horizontal line"""
    def __init__(self, width, color, thickness=2, left_offset=0):
        super().__init__()
        self.width = width
        self.color = color
        self.thickness = thickness
        self.left_offset = left_offset
        self.height = thickness

    def draw(self):
        self.canv.setFillColor(self.color)
        self.canv.rect(self.left_offset, 0, self.width, self.thickness, fill=1, stroke=0)


class SidebarBox(Flowable):
    """A card with colored left border sidebar"""
    def __init__(self, content_lines, accent_color, width, bg_color=None):
        super().__init__()
        self.content_lines = content_lines
        self.accent_color = accent_color
        self.bg_color = bg_color or LIGHT_BG
        self.width = width
        self.height = len(content_lines) * 18 + 24

    def draw(self):
        c = self.canv
        # Background
        c.setFillColor(self.bg_color)
        c.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=0)
        # Left accent bar
        c.setFillColor(self.accent_color)
        c.rect(0, 0, 4, self.height, fill=1, stroke=0)
        # Text
        c.setFillColor(NAVY)
        c.setFont("Helvetica", 10)
        for i, line in enumerate(self.content_lines):
            y = self.height - 18 - i * 18
            c.drawString(14, y, str(line))


class NumberBadge(Flowable):
    """A circular numbered badge"""
    def __init__(self, number, color=ELECTRIC):
        super().__init__()
        self.number = str(number)
        self.color = color
        self.width = 24
        self.height = 24

    def draw(self):
        c = self.canv
        c.setFillColor(self.color)
        c.circle(12, 12, 12, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(12, 8, self.number)


def make_canvas_template(company_name: str, report_date: str):
    """Returns a canvas callback for page headers/footers"""
    def draw_page(canvas, doc):
        canvas.saveState()
        w, h = A4

        # ── Header bar ──────────────────────────────────────────
        canvas.setFillColor(NAVY)
        canvas.rect(0, h - 22*mm, w, 22*mm, fill=1, stroke=0)

        # Accent stripe
        canvas.setFillColor(ELECTRIC)
        canvas.rect(0, h - 22*mm, 6, 22*mm, fill=1, stroke=0)

        # Company name in header
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(16*mm, h - 13*mm, f"{company_name} — Business Intelligence Report")

        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(HexColor("#94A3B8"))
        canvas.drawRightString(w - 12*mm, h - 13*mm, f"Confidential  •  {report_date}")

        # ── Footer ──────────────────────────────────────────────
        canvas.setFillColor(HexColor("#F1F5F9"))
        canvas.rect(0, 0, w, 14*mm, fill=1, stroke=0)

        canvas.setFillColor(ELECTRIC)
        canvas.rect(0, 0, 6, 14*mm, fill=1, stroke=0)

        canvas.setFillColor(SLATE)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(16*mm, 5*mm, "Prepared exclusively for you by our Intelligence Team")
        canvas.drawRightString(w - 12*mm, 5*mm, f"Page {doc.page}")

        canvas.restoreState()

    return draw_page


class ReportGenerator:
    def __init__(self):
        self.output_dir = Path("outputs")
        self.output_dir.mkdir(exist_ok=True)

    async def generate(self, lead, enriched: dict) -> str:
        """Generate PDF report and return file path"""
        loop = asyncio.get_event_loop()
        path = await loop.run_in_executor(None, self._build_pdf, lead, enriched)
        return path

    def _build_pdf(self, lead, data: dict) -> str:
        """Build the PDF synchronously"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_company = "".join(c for c in lead.company if c.isalnum() or c in " _-").strip().replace(" ", "_")
        filename = f"{safe_company}_Audit_Report_{ts}.pdf"
        filepath = str(self.output_dir / filename)

        report_date = datetime.now().strftime("%B %d, %Y")
        page_template = make_canvas_template(lead.company, report_date)

        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=18*mm,
            leftMargin=18*mm,
            topMargin=28*mm,
            bottomMargin=20*mm,
            title=f"{lead.company} Business Audit Report",
            author="Intelligence Team",
        )

        styles = self._build_styles()
        story = []

        # Build sections
        story += self._cover_section(lead, data, styles, report_date)
        story += self._executive_summary(lead, data, styles)
        story += self._company_intelligence(lead, data, styles)
        story += self._audit_findings(data, styles)
        story += self._opportunities_section(data, styles)
        story += self._quick_wins(data, styles)
        story += self._closing_section(lead, data, styles, report_date)

        doc.build(story, onFirstPage=page_template, onLaterPages=page_template)
        logger.info(f"PDF built: {filepath}")
        return filepath

    def _build_styles(self):
        base = getSampleStyleSheet()

        styles = {
            "cover_title": ParagraphStyle(
                "CoverTitle", fontSize=32, textColor=WHITE, fontName="Helvetica-Bold",
                leading=38, spaceAfter=6,
            ),
            "cover_sub": ParagraphStyle(
                "CoverSub", fontSize=14, textColor=HexColor("#94A3B8"), fontName="Helvetica",
                leading=20, spaceAfter=4,
            ),
            "section_header": ParagraphStyle(
                "SectionHeader", fontSize=16, textColor=NAVY, fontName="Helvetica-Bold",
                leading=22, spaceBefore=18, spaceAfter=8,
            ),
            "sub_header": ParagraphStyle(
                "SubHeader", fontSize=12, textColor=ELECTRIC, fontName="Helvetica-Bold",
                leading=16, spaceBefore=10, spaceAfter=4,
            ),
            "body": ParagraphStyle(
                "Body", fontSize=10, textColor=SLATE, fontName="Helvetica",
                leading=16, spaceAfter=6, alignment=TA_JUSTIFY,
            ),
            "body_dark": ParagraphStyle(
                "BodyDark", fontSize=10, textColor=MIDNIGHT, fontName="Helvetica",
                leading=16, spaceAfter=6,
            ),
            "bullet_item": ParagraphStyle(
                "BulletItem", fontSize=10, textColor=SLATE, fontName="Helvetica",
                leading=16, leftIndent=12, spaceAfter=4,
                bulletText="▸", bulletIndent=0,
            ),
            "tag": ParagraphStyle(
                "Tag", fontSize=8, textColor=ELECTRIC, fontName="Helvetica-Bold",
                leading=12, spaceAfter=2,
            ),
            "caption": ParagraphStyle(
                "Caption", fontSize=8, textColor=HexColor("#94A3B8"), fontName="Helvetica",
                leading=12, alignment=TA_CENTER,
            ),
            "highlight": ParagraphStyle(
                "Highlight", fontSize=11, textColor=NAVY, fontName="Helvetica-Bold",
                leading=16, spaceAfter=6,
            ),
            "finding_title": ParagraphStyle(
                "FindingTitle", fontSize=11, textColor=NAVY, fontName="Helvetica-Bold",
                leading=15, spaceAfter=3,
            ),
            "finding_text": ParagraphStyle(
                "FindingText", fontSize=10, textColor=SLATE, fontName="Helvetica",
                leading=15, spaceAfter=4,
            ),
            "rec_text": ParagraphStyle(
                "RecText", fontSize=10, textColor=HexColor("#065F46"), fontName="Helvetica",
                leading=15, leftIndent=8,
            ),
            "metric_num": ParagraphStyle(
                "MetricNum", fontSize=22, textColor=ELECTRIC, fontName="Helvetica-Bold",
                leading=26, alignment=TA_CENTER,
            ),
            "metric_label": ParagraphStyle(
                "MetricLabel", fontSize=9, textColor=SLATE, fontName="Helvetica",
                leading=13, alignment=TA_CENTER,
            ),
        }
        return styles

    def _cover_section(self, lead, data, styles, report_date):
        """Full cover page with navy background feel"""
        story = []

        # Big decorative header block
        cover_data = [[
            Paragraph(f"BUSINESS<br/>INTELLIGENCE<br/>AUDIT", styles["cover_title"]),
        ]]
        cover_table = Table(cover_data, colWidths=[174*mm])
        cover_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("TOPPADDING", (0, 0), (-1, -1), 20),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
            ("LEFTPADDING", (0, 0), (-1, -1), 16),
            ("RIGHTPADDING", (0, 0), (-1, -1), 16),
            ("ROUNDEDCORNERS", [6]),
        ]))
        story.append(cover_table)
        story.append(Spacer(1, 8))

        # Electric accent line
        story.append(ColoredLine(174*mm, ELECTRIC, thickness=4))
        story.append(Spacer(1, 4))
        story.append(ColoredLine(60*mm, CYAN, thickness=2))
        story.append(Spacer(1, 20))

        # Company name & recipient
        story.append(Paragraph(f"Prepared exclusively for", ParagraphStyle(
            "PrepFor", fontSize=10, textColor=SLATE, fontName="Helvetica", leading=14,
        )))
        story.append(Spacer(1, 4))
        story.append(Paragraph(lead.company.upper(), ParagraphStyle(
            "CompanyName", fontSize=26, textColor=NAVY, fontName="Helvetica-Bold", leading=30,
        )))
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"Attention: {lead.name}  •  {lead.role or 'Leadership Team'}", ParagraphStyle(
            "Attention", fontSize=11, textColor=ELECTRIC, fontName="Helvetica", leading=15,
        )))
        story.append(Spacer(1, 24))

        # Meta info cards in a row
        industry = data.get("industry", lead.industry or "Technology")
        biz_model = data.get("business_model", "B2B")
        size = data.get("estimated_size", lead.company_size or "N/A")

        meta_data = [[
            [Paragraph("INDUSTRY", styles["tag"]), Paragraph(industry[:30], styles["highlight"])],
            [Paragraph("BUSINESS MODEL", styles["tag"]), Paragraph(biz_model[:25], styles["highlight"])],
            [Paragraph("COMPANY SIZE", styles["tag"]), Paragraph(size[:20], styles["highlight"])],
        ]]
        meta_table = Table(meta_data[0], colWidths=[58*mm, 58*mm, 58*mm])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("BOX", (0, 0), (0, 0), 1, BORDER),
            ("BOX", (1, 0), (1, 0), 1, BORDER),
            ("BOX", (2, 0), (2, 0), 1, BORDER),
            ("ROUNDEDCORNERS", [4]),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 20))

        # Date & report type
        story.append(Paragraph(f"Report Date: {report_date}", ParagraphStyle(
            "DateStyle", fontSize=9, textColor=HexColor("#94A3B8"), fontName="Helvetica", leading=13,
        )))
        story.append(Paragraph("Confidential — For Recipient Use Only", ParagraphStyle(
            "Conf", fontSize=9, textColor=HexColor("#94A3B8"), fontName="Helvetica", leading=13,
        )))

        story.append(PageBreak())
        return story

    def _executive_summary(self, lead, data, styles):
        story = []
        story.append(Paragraph("Executive Summary", styles["section_header"]))
        story.append(ColoredLine(174*mm, ELECTRIC, thickness=2))
        story.append(Spacer(1, 12))

        # Personalized intro
        intro = data.get("personalized_intro", f"Dear {lead.name}, thank you for your interest.")
        intro_box = [[Paragraph(intro, ParagraphStyle(
            "IntroBox", fontSize=11, textColor=MIDNIGHT, fontName="Helvetica",
            leading=18, alignment=TA_JUSTIFY,
        ))]]
        intro_table = Table(intro_box, colWidths=[174*mm])
        intro_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#EFF6FF")),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("LINEAFTER", (0, 0), (0, -1), 4, ELECTRIC),
            ("ROUNDEDCORNERS", [4]),
        ]))
        story.append(intro_table)
        story.append(Spacer(1, 12))

        # Executive summary text
        exec_summary = data.get("executive_summary", "")
        if exec_summary:
            story.append(Paragraph(exec_summary, styles["body"]))
        story.append(Spacer(1, 10))

        # Headline insight box
        headline = data.get("headline_insight", "")
        if headline:
            hl_data = [[
                Paragraph("💡  KEY INSIGHT", ParagraphStyle(
                    "InsightLabel", fontSize=8, textColor=ELECTRIC, fontName="Helvetica-Bold", leading=12,
                )),
            ], [
                Paragraph(headline, ParagraphStyle(
                    "InsightText", fontSize=11, textColor=NAVY, fontName="Helvetica-Bold",
                    leading=17, alignment=TA_JUSTIFY,
                )),
            ]]
            hl_table = Table(hl_data, colWidths=[174*mm])
            hl_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#EEF2FF")),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("ROUNDEDCORNERS", [4]),
                ("LINEBEFORE", (0, 0), (0, -1), 4, ACCENT),
            ]))
            story.append(hl_table)

        return story

    def _company_intelligence(self, lead, data, styles):
        story = []
        story.append(Spacer(1, 18))
        story.append(Paragraph("Company Intelligence", styles["section_header"]))
        story.append(ColoredLine(174*mm, CYAN, thickness=2))
        story.append(Spacer(1, 12))

        # Company overview
        overview = data.get("company_overview", "")
        if overview:
            story.append(Paragraph("Company Overview", styles["sub_header"]))
            story.append(Paragraph(overview, styles["body"]))
            story.append(Spacer(1, 8))

        # Key facts in 2-col grid
        facts_left = [
            ("Value Proposition", data.get("value_proposition", "N/A")),
            ("Business Model", data.get("business_model", "N/A")),
            ("Target Customers", data.get("target_customers", "N/A")),
        ]
        facts_right = [
            ("Market Position", data.get("market_position", "N/A")),
            ("Tech Stack", data.get("tech_stack_hints", "N/A")),
            ("Social Presence", data.get("social_presence", "N/A")),
        ]

        def fact_cell(label, value):
            return [
                Paragraph(label.upper(), styles["tag"]),
                Paragraph(str(value)[:150], styles["body_dark"]),
            ]

        rows = []
        for (ll, lv), (rl, rv) in zip(facts_left, facts_right):
            left_cell = fact_cell(ll, lv)
            right_cell = fact_cell(rl, rv)
            row_table_l = Table([[left_cell[0]], [left_cell[1]]], colWidths=[82*mm])
            row_table_r = Table([[right_cell[0]], [right_cell[1]]], colWidths=[82*mm])
            row_table_l.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
            ]))
            row_table_r.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
            ]))
            rows.append([row_table_l, row_table_r])

        if rows:
            grid = Table(rows, colWidths=[87*mm, 87*mm], spaceBefore=4, spaceAfter=4)
            grid.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(grid)
            story.append(Spacer(1, 10))

        # Products & Services
        services = data.get("key_products_services", [])
        if services:
            story.append(Paragraph("Products & Services", styles["sub_header"]))
            svc_items = []
            for svc in services[:6]:
                svc_items.append([
                    Paragraph("▸", ParagraphStyle("Bullet", fontSize=11, textColor=ELECTRIC, fontName="Helvetica-Bold", leading=15)),
                    Paragraph(str(svc), styles["body_dark"]),
                ])
            svc_table = Table(svc_items, colWidths=[8*mm, 162*mm])
            svc_table.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(svc_table)
            story.append(Spacer(1, 10))

        # Competitive landscape
        comp = data.get("competitor_landscape", "")
        if comp:
            story.append(Paragraph("Competitive Landscape", styles["sub_header"]))
            story.append(Paragraph(str(comp), styles["body"]))

        # Recent developments
        recent = data.get("recent_developments", "")
        if recent and recent.lower() not in ["no recent news found.", "n/a", ""]:
            story.append(Spacer(1, 8))
            story.append(Paragraph("Recent Developments", styles["sub_header"]))
            story.append(Paragraph(str(recent), styles["body"]))

        return story

    def _audit_findings(self, data, styles):
        story = []
        story.append(Spacer(1, 18))
        story.append(Paragraph("Detailed Audit Findings", styles["section_header"]))
        story.append(ColoredLine(174*mm, WARNING, thickness=2))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "Our analysis identified the following key areas requiring attention:",
            styles["body"],
        ))
        story.append(Spacer(1, 12))

        findings = data.get("audit_findings", [])
        for i, finding in enumerate(findings):
            if not isinstance(finding, dict):
                continue
            area = finding.get("area", "Area")
            text = finding.get("finding", "")
            impact = finding.get("impact", "Medium")
            rec = finding.get("recommendation", "")
            impact_color = IMPACT_COLORS.get(impact, WARNING)
            impact_bg = IMPACT_BG.get(impact, HexColor("#FFFBEB"))

            # Finding card
            header_row = [
                [
                    Paragraph(f"{i+1}. {area}", styles["finding_title"]),
                    Paragraph(impact.upper(), ParagraphStyle(
                        "ImpactBadge", fontSize=9, textColor=impact_color,
                        fontName="Helvetica-Bold", leading=12, alignment=TA_RIGHT,
                    )),
                ]
            ]
            header_table = Table(header_row, colWidths=[130*mm, 34*mm])
            header_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))

            body_content = [
                [Paragraph(str(text), styles["finding_text"])],
            ]
            if rec:
                body_content.append([
                    Paragraph(f"→ Recommendation: {rec}", styles["rec_text"]),
                ])
            body_table = Table(body_content, colWidths=[164*mm])
            body_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("BACKGROUND", (-1, -1), (-1, -1), HexColor("#F0FDF4")),
            ]))

            # Wrap in outer card with left accent
            card_data = [[header_table], [body_table]]
            card = Table(card_data, colWidths=[174*mm])
            card.setStyle(TableStyle([
                ("LINEBEFORE", (0, 0), (0, -1), 4, impact_color),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(KeepTogether([card, Spacer(1, 8)]))

        return story

    def _opportunities_section(self, data, styles):
        story = []
        story.append(Spacer(1, 18))
        story.append(Paragraph("Growth Opportunities", styles["section_header"]))
        story.append(ColoredLine(174*mm, SUCCESS, thickness=2))
        story.append(Spacer(1, 10))

        # Pain points + opportunities side by side
        pain_points = data.get("pain_points", [])
        opportunities = data.get("growth_opportunities", [])

        def make_list_cells(items, color, icon="●"):
            cells = []
            for item in items[:5]:
                cells.append(Paragraph(f"{icon}  {item}", ParagraphStyle(
                    "ListItem", fontSize=10, textColor=SLATE, fontName="Helvetica",
                    leading=15, leftIndent=4, spaceAfter=5,
                )))
            return cells

        pp_header = Paragraph("Current Pain Points", ParagraphStyle(
            "PPHeader", fontSize=12, textColor=DANGER, fontName="Helvetica-Bold", leading=16,
        ))
        opp_header = Paragraph("Growth Opportunities", ParagraphStyle(
            "OppHeader", fontSize=12, textColor=SUCCESS, fontName="Helvetica-Bold", leading=16,
        ))

        pp_items = make_list_cells(pain_points, DANGER, "✗")
        opp_items = make_list_cells(opportunities, SUCCESS, "✓")

        two_col = [[
            [pp_header, Spacer(1, 6)] + pp_items,
            [opp_header, Spacer(1, 6)] + opp_items,
        ]]

        def col_table(content, bg, border_color):
            t = Table([[c] for c in content], colWidths=[80*mm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("LINEBEFORE", (0, 0), (0, -1), 3, border_color),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            return t

        left_col = col_table([pp_header] + pp_items, HexColor("#FFF5F5"), DANGER)
        right_col = col_table([opp_header] + opp_items, HexColor("#F0FDF4"), SUCCESS)

        two_col_table = Table([[left_col, right_col]], colWidths=[87*mm, 87*mm])
        two_col_table.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(two_col_table)

        return story

    def _quick_wins(self, data, styles):
        story = []
        story.append(Spacer(1, 18))
        story.append(Paragraph("Recommended Quick Wins", styles["section_header"]))
        story.append(ColoredLine(174*mm, ACCENT, thickness=2))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "These high-impact actions can be implemented immediately with minimal investment:",
            styles["body"],
        ))
        story.append(Spacer(1, 10))

        wins = data.get("quick_wins", [])
        for i, win in enumerate(wins[:5]):
            win_row = [[
                Paragraph(str(i + 1), ParagraphStyle(
                    "WinNum", fontSize=14, textColor=WHITE, fontName="Helvetica-Bold",
                    leading=18, alignment=TA_CENTER,
                )),
                Paragraph(str(win), styles["body_dark"]),
            ]]
            win_table = Table(win_row, colWidths=[12*mm, 158*mm])
            win_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), ACCENT),
                ("BACKGROUND", (1, 0), (1, 0), WHITE),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (0, 0), 3),
                ("RIGHTPADDING", (0, 0), (0, 0), 3),
                ("LEFTPADDING", (1, 0), (1, 0), 12),
                ("RIGHTPADDING", (1, 0), (1, 0), 12),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(KeepTogether([win_table, Spacer(1, 6)]))

        return story

    def _closing_section(self, lead, data, styles, report_date):
        story = []
        story.append(Spacer(1, 24))
        story.append(ColoredLine(174*mm, NAVY, thickness=1))
        story.append(Spacer(1, 16))

        # CTA box
        cta_data = [[
            Paragraph("Ready to Accelerate Your Growth?", ParagraphStyle(
                "CTATitle", fontSize=16, textColor=WHITE, fontName="Helvetica-Bold",
                leading=20, alignment=TA_CENTER,
            )),
        ], [
            Paragraph(
                f"This report was prepared specifically for {lead.company} based on our research. "
                f"We'd love to discuss these findings with {lead.name} and chart a clear path forward.",
                ParagraphStyle(
                    "CTABody", fontSize=10, textColor=HexColor("#CBD5E1"), fontName="Helvetica",
                    leading=16, alignment=TA_CENTER,
                ),
            ),
        ], [
            Paragraph("Schedule a Free Strategy Call →", ParagraphStyle(
                "CTAButton", fontSize=11, textColor=CYAN, fontName="Helvetica-Bold",
                leading=16, alignment=TA_CENTER,
            )),
        ]]
        cta_table = Table(cta_data, colWidths=[174*mm])
        cta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("TOPPADDING", (0, 0), (-1, -1), 16),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
            ("LEFTPADDING", (0, 0), (-1, -1), 20),
            ("RIGHTPADDING", (0, 0), (-1, -1), 20),
            ("ROUNDEDCORNERS", [6]),
        ]))
        story.append(cta_table)

        story.append(Spacer(1, 16))
        story.append(Paragraph(
            f"Report generated on {report_date} for {lead.email}  •  Confidential",
            styles["caption"],
        ))
        return story
