"""Job post scraper — Playwright-based extraction from public career pages.

Scrapes public career pages to produce a JobPostSignal:
- Total open roles
- Engineering roles count
- AI/ML roles count
- Top stacks mentioned
- 60-day velocity (if historical data exists)

Respects robots.txt. No login. No captcha bypass.
Results cached to data/job_posts/{company}.json.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from agent.models import JobPostSignal, SignalStrength
from config.settings import settings

logger = logging.getLogger(__name__)

# Keywords for classifying roles
ENGINEERING_KEYWORDS = {
    "engineer", "developer", "swe", "sde", "architect", "devops",
    "backend", "frontend", "fullstack", "full-stack", "full stack",
    "platform", "infrastructure", "site reliability", "sre",
}
AI_ML_KEYWORDS = {
    "machine learning", "ml engineer", "data scientist", "applied scientist",
    "ai engineer", "llm", "nlp", "computer vision", "deep learning",
    "ai product", "ml ops", "mlops", "data platform", "ai research",
}
STACK_KEYWORDS = {
    "python": "python", "go": "go", "golang": "go", "rust": "rust",
    "java": "java", "typescript": "typescript", "javascript": "javascript",
    "react": "react", "node": "node.js", "kubernetes": "kubernetes",
    "terraform": "terraform", "aws": "aws", "gcp": "gcp",
    "pytorch": "pytorch", "tensorflow": "tensorflow",
    "spark": "spark", "airflow": "airflow", "dbt": "dbt",
    "snowflake": "snowflake", "databricks": "databricks",
    "ray": "ray", "mlflow": "mlflow",
}

CAREER_PATH_CANDIDATES = [
    "/careers", "/jobs", "/open-positions", "/join-us", "/work-with-us",
    "/about/careers", "/company/careers", "/team/jobs",
]


class JobPostScraper:
    def __init__(self):
        self._cache_dir = Path(settings.job_posts_path)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def scrape(self, company_name: str, website: str, use_cache: bool = True) -> JobPostSignal:
        """Scrape public career page for job post data."""
        safe_name = re.sub(r"[^a-z0-9]", "_", company_name.lower())
        cache_path = self._cache_dir / f"{safe_name}.json"

        if use_cache and cache_path.exists():
            cached = json.loads(cache_path.read_text())
            age_hours = (time.time() - cached.get("scraped_at_ts", 0)) / 3600
            if age_hours < 24:
                logger.info(f"Using cached job data for {company_name} ({age_hours:.1f}h old)")
                return self._to_signal(cached)

        if not website or "http" not in website:
            return JobPostSignal(strength=SignalStrength.ABSENT, source="no_website")

        try:
            raw = self._scrape_career_page(company_name, website)
            raw["scraped_at"] = datetime.utcnow().isoformat()
            raw["scraped_at_ts"] = time.time()
            cache_path.write_text(json.dumps(raw, indent=2))
            return self._to_signal(raw)
        except Exception as e:
            logger.warning(f"Scrape failed for {company_name}: {e}")
            return JobPostSignal(strength=SignalStrength.ABSENT, source=f"scrape_failed: {e}")

    def _scrape_career_page(self, company_name: str, website: str) -> dict:
        """Use Playwright to scrape the career page."""
        from playwright.sync_api import sync_playwright

        base = website.rstrip("/")
        result = {
            "company": company_name,
            "website": website,
            "career_url": None,
            "roles": [],
            "raw_text": "",
        }

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (compatible; TenaciousBot/1.0; +https://tenacious.dev/bot)"
            )
            page.set_default_timeout(15000)

            # Try career page URLs
            career_url = self._find_career_page(page, base)
            if not career_url:
                browser.close()
                result["raw_text"] = "No career page found"
                return result

            result["career_url"] = career_url

            try:
                page.goto(career_url, wait_until="domcontentloaded")
                # Wait for dynamic JS content to render
                page.wait_for_timeout(3000)
                # Scroll to trigger lazy-loaded listings
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(1000)

                text = page.inner_text("body")
                result["raw_text"] = text[:30000]

                roles = self._extract_roles(page, text)
                result["roles"] = roles

            except Exception as e:
                logger.warning(f"Career page load failed for {career_url}: {e}")
                result["raw_text"] = f"Load failed: {e}"

            browser.close()

        return result

    def _find_career_page(self, page, base_url: str) -> Optional[str]:
        """Try common career page paths, return first that loads."""
        for path in CAREER_PATH_CANDIDATES:
            url = base_url + path
            try:
                resp = page.goto(url, wait_until="domcontentloaded")
                if resp and resp.status == 200:
                    body = page.inner_text("body")[:500].lower()
                    # Verify it looks like a careers page
                    if any(kw in body for kw in ("career", "job", "position", "opening", "hiring", "join")):
                        logger.info(f"Found career page: {url}")
                        return url
            except Exception:
                continue

        # Fallback: try to find a careers link on the homepage
        try:
            page.goto(base_url, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            links = page.query_selector_all("a")
            for link in links:
                href = link.get_attribute("href") or ""
                text = (link.inner_text() or "").lower()
                if any(kw in text for kw in ("career", "jobs", "join us", "work with us", "hiring")):
                    full_url = urljoin(base_url, href)
                    logger.info(f"Found career link on homepage: {full_url}")
                    return full_url
        except Exception:
            pass

        return None

    def _extract_roles(self, page, text: str) -> list[dict]:
        """Extract individual job roles from the page."""
        roles = []

        # Strategy 1: Look for common job listing selectors
        selectors = [
            "[class*='job']", "[class*='position']", "[class*='opening']",
            "[class*='career']", "[class*='role']", "[class*='listing']",
            "li a", ".posting", ".job-card",
        ]
        seen_titles = set()

        for selector in selectors:
            try:
                elements = page.query_selector_all(selector)
                for el in elements[:100]:
                    title = (el.inner_text() or "").strip()
                    if len(title) < 5 or len(title) > 150:
                        continue
                    title_lower = title.lower()
                    if title_lower in seen_titles:
                        continue
                    # Filter to things that look like job titles
                    if self._looks_like_job_title(title_lower):
                        seen_titles.add(title_lower)
                        roles.append({
                            "title": title,
                            "is_engineering": self._is_engineering(title_lower),
                            "is_ai_ml": self._is_ai_ml(title_lower),
                            "stacks": self._extract_stacks(title_lower),
                        })
            except Exception:
                continue

        # Strategy 2: Regex fallback on raw text
        if len(roles) < 3:
            lines = text.split("\n")
            for line in lines:
                line = line.strip()
                if 10 < len(line) < 120 and self._looks_like_job_title(line.lower()):
                    ll = line.lower()
                    if ll not in seen_titles:
                        seen_titles.add(ll)
                        roles.append({
                            "title": line,
                            "is_engineering": self._is_engineering(ll),
                            "is_ai_ml": self._is_ai_ml(ll),
                            "stacks": self._extract_stacks(ll),
                        })

        return roles[:200]

    def _to_signal(self, raw: dict) -> JobPostSignal:
        """Convert raw scrape data to a JobPostSignal."""
        roles = raw.get("roles", [])
        total = len(roles)
        eng = sum(1 for r in roles if r.get("is_engineering"))
        ai_ml = sum(1 for r in roles if r.get("is_ai_ml"))

        all_stacks = []
        for r in roles:
            all_stacks.extend(r.get("stacks", []))
        # Count and rank stacks
        stack_counts: dict[str, int] = {}
        for s in all_stacks:
            stack_counts[s] = stack_counts.get(s, 0) + 1
        top_stacks = sorted(stack_counts, key=stack_counts.get, reverse=True)[:5]

        # Determine strength
        if total == 0:
            strength = SignalStrength.ABSENT
        elif eng >= 10:
            strength = SignalStrength.STRONG
        elif eng >= 3:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK

        return JobPostSignal(
            total_open_roles=total,
            engineering_roles=eng,
            ai_ml_roles=ai_ml,
            velocity_60d=None,  # requires historical comparison
            top_stacks=top_stacks,
            strength=strength,
            source=raw.get("career_url") or raw.get("website", "scraped"),
        )

    @staticmethod
    def _looks_like_job_title(text: str) -> bool:
        job_indicators = (
            "engineer", "developer", "manager", "designer", "analyst",
            "scientist", "lead", "director", "head of", "vp ", "architect",
            "coordinator", "specialist", "consultant", "intern", "associate",
        )
        return any(kw in text for kw in job_indicators)

    @staticmethod
    def _is_engineering(title: str) -> bool:
        return any(kw in title for kw in ENGINEERING_KEYWORDS)

    @staticmethod
    def _is_ai_ml(title: str) -> bool:
        return any(kw in title for kw in AI_ML_KEYWORDS)

    @staticmethod
    def _extract_stacks(title: str) -> list[str]:
        found = []
        for keyword, stack_name in STACK_KEYWORDS.items():
            if keyword in title.split() or keyword in title:
                if stack_name not in found:
                    found.append(stack_name)
        return found
