"""Enhanced scraper using Scrapling — replaces raw Playwright for job posts and leadership detection.

Adds LinkedIn company page scraping for:
- Hiring signals (recent job posts, headcount changes)
- Leadership changes (new CTO/VP Eng announcements)
- Company updates and growth signals

Uses Scrapling's StealthyFetcher for anti-bot bypass on LinkedIn,
and Fetcher for standard career pages.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

from scrapling import Fetcher, StealthyFetcher

from agent.models import JobPostSignal, LeadershipSignal, SignalStrength
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
}
LEADERSHIP_TITLES = {
    "cto", "chief technology officer",
    "vp engineering", "vp of engineering", "vice president engineering",
    "head of engineering", "head of technology",
}
CAREER_PATHS = [
    "/careers", "/jobs", "/open-positions", "/join-us",
    "/about/careers", "/company/careers",
]


class ScraplingEnricher:
    """Unified scraper using Scrapling for career pages + LinkedIn."""

    def __init__(self):
        self._cache_dir = Path(settings.job_posts_path)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._fetcher = Fetcher()
        self._stealth = None  # Lazy-init StealthyFetcher for LinkedIn

    def _get_stealth(self):
        if self._stealth is None:
            self._stealth = StealthyFetcher()
        return self._stealth

    # ─── PUBLIC API ───────────────────────────────────────────────

    def scrape_jobs(self, company_name: str, website: str = "", linkedin_url: str = "") -> JobPostSignal:
        """Scrape job posts from career page + LinkedIn. Returns combined signal."""
        safe_name = re.sub(r"[^a-z0-9]", "_", company_name.lower())
        cache_path = self._cache_dir / f"{safe_name}_scrapling.json"

        # Check cache (24h TTL)
        if cache_path.exists():
            cached = json.loads(cache_path.read_text())
            age_hours = (time.time() - cached.get("scraped_at_ts", 0)) / 3600
            if age_hours < 24:
                logger.info(f"Cache hit for {company_name} ({age_hours:.1f}h old)")
                return self._to_job_signal(cached)

        roles = []

        # Source 1: Career page
        if website:
            career_roles = self._scrape_career_page(company_name, website)
            roles.extend(career_roles)

        # Source 2: LinkedIn jobs
        if linkedin_url:
            linkedin_roles = self._scrape_linkedin_jobs(company_name, linkedin_url)
            roles.extend(linkedin_roles)

        # Deduplicate by title
        seen = set()
        unique_roles = []
        for role in roles:
            title_key = role["title"].lower().strip()
            if title_key not in seen:
                seen.add(title_key)
                unique_roles.append(role)

        # Cache result
        result = {
            "company": company_name,
            "roles": unique_roles,
            "sources": [],
            "scraped_at": datetime.utcnow().isoformat(),
            "scraped_at_ts": time.time(),
        }
        if website:
            result["sources"].append(f"career_page:{website}")
        if linkedin_url:
            result["sources"].append(f"linkedin:{linkedin_url}")

        cache_path.write_text(json.dumps(result, indent=2))
        return self._to_job_signal(result)

    def scrape_leadership(self, company_name: str, website: str = "", linkedin_url: str = "") -> LeadershipSignal:
        """Detect leadership changes from press pages + LinkedIn."""

        # Source 1: Company press/about pages
        if website:
            signal = self._scrape_press_for_leadership(company_name, website)
            if signal.strength != SignalStrength.ABSENT:
                return signal

        # Source 2: LinkedIn company updates
        if linkedin_url:
            signal = self._scrape_linkedin_leadership(company_name, linkedin_url)
            if signal.strength != SignalStrength.ABSENT:
                return signal

        return LeadershipSignal(strength=SignalStrength.ABSENT, source="no_signal_found")

    # ─── CAREER PAGE SCRAPING ─────────────────────────────────────

    def _scrape_career_page(self, company_name: str, website: str) -> list[dict]:
        """Scrape career page using Scrapling Fetcher."""
        base = website.rstrip("/")
        roles = []

        for path in CAREER_PATHS:
            url = base + path
            try:
                page = self._fetcher.get(url)
                if page.status == 200:
                    text = page.get_all_text() if hasattr(page, 'get_all_text') else page.text
                    # Check if it looks like a careers page
                    if any(kw in text.lower()[:500] for kw in ("career", "job", "position", "opening")):
                        roles = self._extract_roles_from_text(text)
                        if roles:
                            logger.info(f"Found {len(roles)} roles at {url}")
                            break
            except Exception as e:
                logger.debug(f"Career page {url} failed: {e}")
                continue

        return roles

    def _extract_roles_from_text(self, text: str) -> list[dict]:
        """Extract job roles from page text."""
        roles = []
        seen = set()
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            if 10 < len(line) < 120 and self._looks_like_job_title(line.lower()):
                ll = line.lower()
                if ll not in seen:
                    seen.add(ll)
                    roles.append({
                        "title": line,
                        "is_engineering": self._is_engineering(ll),
                        "is_ai_ml": self._is_ai_ml(ll),
                        "stacks": self._extract_stacks(ll),
                        "source": "career_page",
                    })

        return roles[:200]

    # ─── LINKEDIN SCRAPING ────────────────────────────────────────

    def _scrape_linkedin_jobs(self, company_name: str, linkedin_url: str) -> list[dict]:
        """Scrape LinkedIn company jobs using public jobs search URL."""
        roles = []

        # LinkedIn public jobs search (doesn't require auth)
        # Format: https://www.linkedin.com/jobs/search/?keywords=company_name
        company_slug = linkedin_url.rstrip("/").split("/")[-1]
        jobs_urls = [
            f"https://www.linkedin.com/jobs/search/?keywords={company_slug}&f_C={company_slug}",
            linkedin_url.rstrip("/") + "/jobs/",
        ]

        for jobs_url in jobs_urls:
            try:
                stealth = self._get_stealth()
                page = stealth.get(jobs_url)

                if page.status == 200:
                    text = page.get_all_text() if hasattr(page, 'get_all_text') else page.text
                    roles = self._extract_linkedin_roles(text)
                    if roles:
                        logger.info(f"LinkedIn: Found {len(roles)} roles for {company_name}")
                        break
                elif page.status == 999:
                    logger.warning(f"LinkedIn blocked request for {company_name} (status 999)")
                else:
                    logger.debug(f"LinkedIn returned {page.status} for {jobs_url}")

            except Exception as e:
                logger.warning(f"LinkedIn scrape failed for {company_name}: {e}")

        return roles

    def _extract_linkedin_roles(self, text: str) -> list[dict]:
        """Extract job roles from LinkedIn page text."""
        roles = []
        seen = set()
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            if 10 < len(line) < 120 and self._looks_like_job_title(line.lower()):
                ll = line.lower()
                if ll not in seen:
                    seen.add(ll)
                    roles.append({
                        "title": line,
                        "is_engineering": self._is_engineering(ll),
                        "is_ai_ml": self._is_ai_ml(ll),
                        "stacks": self._extract_stacks(ll),
                        "source": "linkedin",
                    })

        return roles[:200]

    def _scrape_linkedin_leadership(self, company_name: str, linkedin_url: str) -> LeadershipSignal:
        """Check LinkedIn company page for leadership changes."""
        # LinkedIn people page
        people_url = linkedin_url.rstrip("/") + "/people/"

        try:
            stealth = self._get_stealth()
            page = stealth.get(people_url)

            if page.status == 200:
                text = page.get_all_text() if hasattr(page, 'get_all_text') else page.text
                return self._detect_leadership_from_text(text, "linkedin_people")

        except Exception as e:
            logger.warning(f"LinkedIn leadership scrape failed for {company_name}: {e}")

        return LeadershipSignal(strength=SignalStrength.ABSENT, source="linkedin_failed")

    # ─── PRESS PAGE SCRAPING ──────────────────────────────────────

    def _scrape_press_for_leadership(self, company_name: str, website: str) -> LeadershipSignal:
        """Scrape press/news pages for leadership appointment signals."""
        base = website.rstrip("/")
        press_paths = ["/press", "/news", "/blog", "/about", "/about-us", "/company"]

        combined_text = ""
        for path in press_paths:
            try:
                page = self._fetcher.get(base + path)
                if page.status == 200:
                    text = page.get_all_text() if hasattr(page, 'get_all_text') else page.text
                    combined_text += f"\n{text[:10000]}"
            except Exception:
                continue

        if combined_text:
            return self._detect_leadership_from_text(combined_text, "press_page")

        return LeadershipSignal(strength=SignalStrength.ABSENT, source="no_press_page")

    def _detect_leadership_from_text(self, text: str, source: str) -> LeadershipSignal:
        """Detect leadership changes from text content."""
        text_lower = text.lower()

        patterns = [
            r"(?:names?|appoints?|hires?|promotes?|welcomes?)\s+.*?(?:as\s+)?(?:new\s+)?(?:cto|chief technology|vp\s+(?:of\s+)?engineer|head\s+of\s+engineer)",
            r"(?:cto|chief technology|vp\s+(?:of\s+)?engineer|head\s+of\s+engineer).*?(?:joins?|appointed|named|hired)",
            r"new\s+(?:cto|chief technology officer|vp\s+(?:of\s+)?engineering|head\s+of\s+engineering)",
        ]

        for pattern in patterns:
            if re.search(pattern, text_lower):
                # Extract title
                title = None
                for t in sorted(LEADERSHIP_TITLES, key=len, reverse=True):
                    if t in text_lower:
                        title = t.title()
                        break

                return LeadershipSignal(
                    new_leader=True,
                    title=title,
                    strength=SignalStrength.MODERATE,
                    source=source,
                )

        return LeadershipSignal(strength=SignalStrength.ABSENT, source=source)

    # ─── SIGNAL CONVERSION ────────────────────────────────────────

    def _to_job_signal(self, raw: dict) -> JobPostSignal:
        """Convert raw scrape data to JobPostSignal."""
        roles = raw.get("roles", [])
        total = len(roles)
        eng = sum(1 for r in roles if r.get("is_engineering"))
        ai_ml = sum(1 for r in roles if r.get("is_ai_ml"))

        all_stacks = []
        for r in roles:
            all_stacks.extend(r.get("stacks", []))
        stack_counts = {}
        for s in all_stacks:
            stack_counts[s] = stack_counts.get(s, 0) + 1
        top_stacks = sorted(stack_counts, key=stack_counts.get, reverse=True)[:5]

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
            velocity_60d=None,
            top_stacks=top_stacks,
            strength=strength,
            source=", ".join(raw.get("sources", ["scrapling"])),
        )

    # ─── HELPERS ──────────────────────────────────────────────────

    @staticmethod
    def _looks_like_job_title(text: str) -> bool:
        indicators = (
            "engineer", "developer", "manager", "designer", "analyst",
            "scientist", "lead", "director", "head of", "vp ", "architect",
            "specialist", "consultant",
        )
        return any(kw in text for kw in indicators)

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
