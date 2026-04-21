"""Leadership change detector — identifies new CTO/VP Eng appointments.

Two sources:
1. Crunchbase leadership_hire field (structured, preferred)
2. Playwright fallback: scrape company press/blog/about page for appointment signals

Returns a LeadershipSignal that gates Segment 3 classification.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Optional

from agent.models import LeadershipSignal, SignalStrength

logger = logging.getLogger(__name__)

# Titles that indicate engineering leadership changes
TARGET_TITLES = {
    "cto", "chief technology officer",
    "vp engineering", "vp of engineering", "vice president engineering",
    "vp technology", "vice president technology",
    "head of engineering", "head of technology",
    "chief architect", "chief scientist",
    "svp engineering", "svp technology",
}

# Patterns in press headlines that indicate leadership appointments
APPOINTMENT_PATTERNS = [
    r"(?:names?|appoints?|hires?|promotes?|welcomes?)\s+.*?(?:as\s+)?(?:new\s+)?(?:cto|chief technology|vp\s+(?:of\s+)?engineer|head\s+of\s+engineer)",
    r"(?:cto|chief technology|vp\s+(?:of\s+)?engineer|head\s+of\s+engineer).*?(?:joins?|appointed|named|hired)",
    r"new\s+(?:cto|chief technology officer|vp\s+(?:of\s+)?engineering|head\s+of\s+engineering)",
]


class LeadershipDetector:

    def detect_from_crunchbase(self, record: dict) -> LeadershipSignal:
        """Check Crunchbase leadership_hire field for recent engineering leadership changes."""
        raw = record.get("leadership_hire", "")
        if not raw or raw == "EMPTY" or raw == "[]":
            return LeadershipSignal(strength=SignalStrength.ABSENT, source="crunchbase_no_data")

        events = self._parse_json(raw)
        if not isinstance(events, list) or not events:
            return LeadershipSignal(strength=SignalStrength.ABSENT, source="crunchbase_parse_fail")

        best_match = None
        best_recency = 99999

        for event in events:
            label = (event.get("label") or "").lower()
            date_str = event.get("key_event_date") or ""

            if not self._is_engineering_leadership(label):
                continue

            recency = self._compute_recency(date_str)
            if recency is not None and recency < best_recency:
                best_recency = recency
                best_match = event

        if best_match is None:
            return LeadershipSignal(strength=SignalStrength.ABSENT, source="crunchbase_no_eng_leadership")

        name, title = self._extract_name_title(best_match.get("label", ""))

        strength = SignalStrength.ABSENT
        if best_recency <= 90:
            strength = SignalStrength.STRONG
        elif best_recency <= 180:
            strength = SignalStrength.MODERATE
        elif best_recency <= 365:
            strength = SignalStrength.WEAK

        return LeadershipSignal(
            new_leader=True,
            name=name,
            title=title,
            appointed_date=best_match.get("key_event_date", ""),
            recency_days=best_recency if best_recency < 99999 else None,
            strength=strength,
            source=best_match.get("link", "crunchbase_leadership_hire"),
        )

    def detect_from_webpage(self, company_name: str, website: str) -> LeadershipSignal:
        """Fallback: scrape press/about page for leadership appointment signals."""
        if not website or "http" not in website:
            return LeadershipSignal(strength=SignalStrength.ABSENT, source="no_website")

        try:
            text = self._scrape_press_page(website)
            return self._parse_press_text(text, company_name)
        except Exception as e:
            logger.warning(f"Leadership scrape failed for {company_name}: {e}")
            return LeadershipSignal(strength=SignalStrength.ABSENT, source=f"scrape_failed: {e}")

    def detect(self, company_name: str, crunchbase_record: Optional[dict] = None, website: str = "") -> LeadershipSignal:
        """Run detection from all available sources. Crunchbase first, then web fallback."""
        if crunchbase_record:
            signal = self.detect_from_crunchbase(crunchbase_record)
            if signal.strength != SignalStrength.ABSENT:
                return signal

        if website:
            return self.detect_from_webpage(company_name, website)

        return LeadershipSignal(strength=SignalStrength.ABSENT, source="no_sources")

    def _scrape_press_page(self, website: str) -> str:
        """Scrape press/news/about page for leadership text."""
        from playwright.sync_api import sync_playwright

        base = website.rstrip("/")
        press_paths = ["/press", "/news", "/blog", "/about", "/about-us", "/company"]

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (compatible; TenaciousBot/1.0; +https://tenacious.dev/bot)"
            )
            page.set_default_timeout(10000)

            combined_text = ""
            for path in press_paths:
                try:
                    resp = page.goto(base + path, wait_until="domcontentloaded")
                    if resp and resp.status == 200:
                        page.wait_for_timeout(1000)
                        text = page.inner_text("body")[:10000]
                        combined_text += f"\n--- {path} ---\n{text}"
                except Exception:
                    continue

            browser.close()

        return combined_text

    def _parse_press_text(self, text: str, company_name: str) -> LeadershipSignal:
        """Parse scraped text for leadership appointment signals."""
        if not text:
            return LeadershipSignal(strength=SignalStrength.ABSENT, source="empty_press_page")

        text_lower = text.lower()

        for pattern in APPOINTMENT_PATTERNS:
            matches = re.findall(pattern, text_lower)
            if matches:
                # Found an appointment signal — extract details
                name, title = self._extract_from_context(text, matches[0])
                return LeadershipSignal(
                    new_leader=True,
                    name=name,
                    title=title,
                    appointed_date=None,
                    recency_days=None,  # can't determine from text alone
                    strength=SignalStrength.MODERATE,  # moderate because no date
                    source="press_page_scrape",
                )

        return LeadershipSignal(strength=SignalStrength.ABSENT, source="no_appointment_signal")

    @staticmethod
    def _is_engineering_leadership(text: str) -> bool:
        return any(title in text for title in TARGET_TITLES)

    @staticmethod
    def _compute_recency(date_str: str) -> Optional[int]:
        if not date_str:
            return None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                d = datetime.strptime(date_str.strip()[:10], fmt)
                return (datetime.utcnow() - d).days
            except ValueError:
                continue
        return None

    @staticmethod
    def _extract_name_title(label: str) -> tuple[Optional[str], Optional[str]]:
        """Best-effort extraction of person name and title from a headline."""
        label_lower = label.lower()
        title = None
        for t in sorted(TARGET_TITLES, key=len, reverse=True):
            if t in label_lower:
                title = t.title()
                break

        # Try to find a name (capitalized words near the title keyword)
        words = label.split()
        name_parts = []
        for w in words:
            if w[0:1].isupper() and w.lower() not in (
                "new", "names", "appoints", "hires", "as", "the", "and", "of", "for",
                "ceo", "cto", "cfo", "vp", "svp", "president", "chief", "head",
                "officer", "technology", "engineering", "team", "leadership",
            ):
                name_parts.append(w)
        name = " ".join(name_parts[:3]) if name_parts else None

        return name, title

    @staticmethod
    def _extract_from_context(full_text: str, match: str) -> tuple[Optional[str], Optional[str]]:
        """Extract name and title from surrounding context of a regex match."""
        title = None
        for t in sorted(TARGET_TITLES, key=len, reverse=True):
            if t in match.lower():
                title = t.title()
                break
        return None, title  # name extraction from raw text is unreliable

    @staticmethod
    def _parse_json(raw) -> any:
        if isinstance(raw, (list, dict)):
            return raw
        try:
            return json.loads(str(raw))
        except (json.JSONDecodeError, TypeError):
            return None
