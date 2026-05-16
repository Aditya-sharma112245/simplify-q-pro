"""
Company Enrichment Module
Scrapes public web sources + uses Claude to synthesize intelligence
"""

import asyncio
import json
import logging
import os
import re
from typing import Optional
import httpx
from bs4 import BeautifulSoup
import anthropic

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

TIMEOUT = 15


class CompanyEnricher:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    async def enrich(self, lead) -> dict:
        """Orchestrate enrichment from multiple sources"""
        sources_used = []
        raw_data = {}

        # Gather data concurrently
        tasks = {
            "website": self._scrape_website(lead.website or self._guess_website(lead.company)),
            "linkedin": self._search_linkedin(lead.company),
            "news": self._search_news(lead.company),
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for key, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.warning(f"Enrichment source '{key}' failed: {result}")
                raw_data[key] = None
            elif result:
                raw_data[key] = result
                sources_used.append(key)

        # Use Claude to synthesize and analyze
        enriched = await self._synthesize_with_claude(lead, raw_data)
        enriched["sources_used"] = sources_used
        enriched["raw_scraped"] = {k: v for k, v in raw_data.items() if v}

        return enriched

    def _guess_website(self, company_name: str) -> str:
        """Guess website URL from company name"""
        slug = re.sub(r"[^a-z0-9]", "", company_name.lower())
        return f"https://www.{slug}.com"

    async def _scrape_website(self, url: str) -> Optional[dict]:
        """Scrape company website for key info"""
        if not url:
            return None
        
        # Normalize URL
        if not url.startswith("http"):
            url = "https://" + url

        try:
            async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

                # Extract meaningful content
                data = {
                    "url": str(resp.url),
                    "title": soup.title.string.strip() if soup.title else "",
                    "meta_description": "",
                    "hero_text": "",
                    "about_text": "",
                    "services": [],
                    "contact": {},
                }

                # Meta description
                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc:
                    data["meta_description"] = meta_desc.get("content", "")[:500]

                # Hero / headline text
                for tag in ["h1", "h2"]:
                    heroes = soup.find_all(tag)
                    if heroes:
                        data["hero_text"] = " | ".join(
                            h.get_text(strip=True) for h in heroes[:3]
                        )
                        break

                # About section
                about_section = soup.find(
                    lambda t: t.name in ["section", "div", "article"]
                    and any(w in (t.get("class") or []) + [t.get("id", "")] for w in ["about", "mission", "who-we-are", "story"])
                )
                if about_section:
                    data["about_text"] = about_section.get_text(separator=" ", strip=True)[:1000]

                # Services/products mentioned
                service_section = soup.find(
                    lambda t: t.name in ["section", "div"]
                    and any(w in " ".join(t.get("class") or []) + t.get("id", "") for w in ["service", "product", "solution", "offering"])
                )
                if service_section:
                    items = service_section.find_all(["h3", "h4", "li"])
                    data["services"] = [i.get_text(strip=True) for i in items[:10]]

                # Structured body text (first 2000 chars of main content)
                body_text = soup.get_text(separator=" ", strip=True)
                body_text = re.sub(r"\s+", " ", body_text)
                data["body_excerpt"] = body_text[:2500]

                return data

        except Exception as e:
            logger.warning(f"Website scrape failed for {url}: {e}")
            return None

    async def _search_linkedin(self, company: str) -> Optional[dict]:
        """Search for LinkedIn company info via DuckDuckGo"""
        try:
            query = f"{company} company linkedin overview employees founded"
            async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                )
                soup = BeautifulSoup(resp.text, "html.parser")
                results = []
                for r in soup.find_all("div", class_="result__body")[:3]:
                    text = r.get_text(separator=" ", strip=True)
                    if text:
                        results.append(text[:500])
                
                if results:
                    return {"snippets": results}
        except Exception as e:
            logger.warning(f"LinkedIn search failed: {e}")
        return None

    async def _search_news(self, company: str) -> Optional[dict]:
        """Search recent news about the company"""
        try:
            query = f"{company} company news 2024 2025"
            async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query, "df": "y"},  # past year
                )
                soup = BeautifulSoup(resp.text, "html.parser")
                results = []
                for r in soup.find_all("div", class_="result__body")[:5]:
                    title_el = r.find("a", class_="result__a")
                    snippet_el = r.find("a", class_="result__snippet")
                    if title_el or snippet_el:
                        results.append({
                            "title": title_el.get_text(strip=True) if title_el else "",
                            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                        })

                if results:
                    return {"articles": results}
        except Exception as e:
            logger.warning(f"News search failed: {e}")
        return None

    async def _synthesize_with_claude(self, lead, raw_data: dict) -> dict:
        """Use Claude to synthesize enrichment data into structured insights"""
        
        context_parts = []
        if raw_data.get("website"):
            w = raw_data["website"]
            context_parts.append(f"""
WEBSITE DATA:
- URL: {w.get('url', '')}
- Title: {w.get('title', '')}
- Meta Description: {w.get('meta_description', '')}
- Hero Text: {w.get('hero_text', '')}
- About: {w.get('about_text', '')[:500]}
- Services: {', '.join(w.get('services', [])[:8])}
- Body Excerpt: {w.get('body_excerpt', '')[:1500]}
""")

        if raw_data.get("linkedin"):
            context_parts.append(f"""
LINKEDIN/WEB SEARCH DATA:
{chr(10).join(raw_data['linkedin'].get('snippets', []))}
""")

        if raw_data.get("news"):
            articles = raw_data["news"].get("articles", [])
            news_text = "\n".join([f"- {a['title']}: {a['snippet']}" for a in articles[:5]])
            context_parts.append(f"""
RECENT NEWS:
{news_text}
""")

        context = "\n".join(context_parts) if context_parts else "Limited public data available."

        prompt = f"""You are a senior business analyst. Analyze this company and prospect to produce structured intelligence for a personalized audit report.

PROSPECT DETAILS:
- Name: {lead.name}
- Role: {lead.role or 'Not specified'}
- Company: {lead.company}
- Industry: {lead.industry or 'Not specified'}
- Company Size: {lead.company_size or 'Not specified'}
- Challenge: {lead.challenge or 'Not specified'}
- Website: {lead.website or 'Not specified'}

COLLECTED DATA:
{context}

Produce a JSON object with these exact keys. Be specific, insightful, and avoid generic platitudes. If data is unavailable, make reasonable inferences based on company name, industry, and context:

{{
  "company_overview": "2-3 sentence overview of what the company does and their position in the market",
  "industry": "Specific industry/sector (be precise)",
  "business_model": "How they make money - B2B/B2C/SaaS/services/product/etc.",
  "estimated_size": "Estimated team size or revenue range if inferable",
  "founded_approx": "Approximate founding year if known",
  "target_customers": "Who their customers are",
  "key_products_services": ["service1", "service2", "service3"],
  "value_proposition": "Their core value proposition in 1-2 sentences",
  "market_position": "How they position vs competitors (niche, leader, challenger, etc.)",
  "recent_developments": "Any notable recent news, launches, or developments",
  "tech_stack_hints": "Any technology signals from website or public data",
  "social_presence": "Assessment of their online/social media presence",
  "pain_points": [
    "Likely pain point 1 based on their industry and size",
    "Likely pain point 2",
    "Likely pain point 3"
  ],
  "growth_opportunities": [
    "Growth opportunity 1 relevant to their context",
    "Growth opportunity 2",
    "Growth opportunity 3"
  ],
  "audit_findings": [
    {{
      "area": "Digital Presence",
      "finding": "Specific finding about their digital presence",
      "impact": "High/Medium/Low",
      "recommendation": "Specific actionable recommendation"
    }},
    {{
      "area": "Lead Generation",
      "finding": "Specific finding about lead gen",
      "impact": "High/Medium/Low",
      "recommendation": "Specific actionable recommendation"
    }},
    {{
      "area": "Competitive Position",
      "finding": "Finding about market position",
      "impact": "High/Medium/Low",
      "recommendation": "Specific actionable recommendation"
    }},
    {{
      "area": "Technology & Automation",
      "finding": "Finding about tech/automation",
      "impact": "High/Medium/Low",
      "recommendation": "Specific actionable recommendation"
    }},
    {{
      "area": "Customer Experience",
      "finding": "Finding about CX",
      "impact": "High/Medium/Low",
      "recommendation": "Specific actionable recommendation"
    }}
  ],
  "executive_summary": "3-4 sentences personalized executive summary that speaks directly to {lead.name}'s role and challenge. Reference their company specifically.",
  "quick_wins": [
    "Quick win 1 they could implement immediately",
    "Quick win 2",
    "Quick win 3"
  ],
  "competitor_landscape": "Brief description of who they compete with",
  "headline_insight": "One powerful, specific insight about their business that would surprise and impress them",
  "personalized_intro": "A 2-sentence personalized intro paragraph addressed to {lead.name} at {lead.company} acknowledging their specific challenge: '{lead.challenge or 'growing their business'}'"
}}

Return ONLY the JSON object, no markdown, no explanation."""

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4000,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            
            raw_json = response.content[0].text.strip()
            # Strip any accidental markdown fences
            raw_json = re.sub(r"^```json\s*", "", raw_json)
            raw_json = re.sub(r"\s*```$", "", raw_json)
            
            data = json.loads(raw_json)
            logger.info(f"Claude synthesis complete for {lead.company}")
            return data

        except json.JSONDecodeError as e:
            logger.error(f"Claude returned invalid JSON: {e}")
            return self._fallback_enrichment(lead)
        except Exception as e:
            logger.error(f"Claude synthesis failed: {e}")
            return self._fallback_enrichment(lead)

    def _fallback_enrichment(self, lead) -> dict:
        """Fallback when AI synthesis fails"""
        return {
            "company_overview": f"{lead.company} is a company in the {lead.industry or 'technology'} sector.",
            "industry": lead.industry or "Technology",
            "business_model": "B2B Services",
            "estimated_size": lead.company_size or "Unknown",
            "key_products_services": ["Core Service", "Consulting", "Support"],
            "value_proposition": f"Delivering value to customers in the {lead.industry or 'business'} space.",
            "pain_points": ["Scaling operations efficiently", "Lead generation and conversion", "Technology adoption"],
            "growth_opportunities": ["Digital transformation", "Process automation", "Market expansion"],
            "audit_findings": [
                {"area": "Digital Presence", "finding": "Opportunity to strengthen online presence", "impact": "High", "recommendation": "Invest in SEO and content marketing"},
                {"area": "Lead Generation", "finding": "Lead nurturing can be improved", "impact": "Medium", "recommendation": "Implement automated email sequences"},
                {"area": "Technology", "finding": "Automation opportunities exist", "impact": "High", "recommendation": "Adopt CRM and marketing automation tools"},
            ],
            "executive_summary": f"This report provides an analysis of {lead.company} and key recommendations for growth.",
            "quick_wins": ["Improve website SEO", "Set up email automation", "Define ICP clearly"],
            "headline_insight": f"{lead.company} has significant untapped potential in their market segment.",
            "personalized_intro": f"Dear {lead.name}, thank you for reaching out. We've prepared this personalized audit for {lead.company}.",
            "competitor_landscape": "Competitive market with multiple established players.",
            "recent_developments": "No recent news found.",
        }
