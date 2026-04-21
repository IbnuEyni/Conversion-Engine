"""Crunchbase ODM enrichment — firmographics + funding signals.

Reads the 1,000-record Bright Data sample (CSV-derived JSON).
Fields: name, id, uuid, about, industries, num_employees, country_code,
        website, founded_date, funding_rounds_list, financials_highlights, etc.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from agent.models import FundingSignal, SignalStrength
from config.settings import settings


class CrunchbaseEnricher:
    def __init__(self):
        self._data: list[dict] = []
        self._index: dict[str, dict] = {}

    def load(self, path: Optional[str] = None):
        p = Path(path or settings.crunchbase_data_path)
        if not p.exists():
            return
        raw = json.loads(p.read_text())
        self._data = raw if isinstance(raw, list) else []
        for rec in self._data:
            name = (rec.get("name") or "").strip().lower()
            if name:
                self._index[name] = rec

    @property
    def count(self) -> int:
        return len(self._data)

    def find_company(self, name: str) -> Optional[dict]:
        key = name.strip().lower()
        if key in self._index:
            return self._index[key]
        for k, v in self._index.items():
            if key in k or k in key:
                return v
        return None

    def get_firmographics(self, name: str) -> dict:
        rec = self.find_company(name)
        if not rec:
            return {}
        return {
            "crunchbase_id": rec.get("uuid") or rec.get("id", ""),
            "name": rec.get("name", ""),
            "description": rec.get("about") or rec.get("full_description", ""),
            "industry": self._parse_industries(rec),
            "employee_count": self._parse_employees(rec),
            "location": self._parse_location(rec),
            "website": rec.get("website", ""),
            "founded_date": rec.get("founded_date", ""),
            "operating_status": rec.get("operating_status", ""),
        }

    def get_funding_signal(self, name: str) -> FundingSignal:
        rec = self.find_company(name)
        if not rec:
            return FundingSignal(strength=SignalStrength.ABSENT)

        financials = self._parse_json_field(rec.get("financials_highlights", ""))
        rounds = self._parse_json_field(rec.get("funding_rounds_list", ""))

        funding_total = 0
        if isinstance(financials, dict):
            ft = financials.get("funding_total", {})
            funding_total = ft.get("value_usd", 0) or ft.get("value", 0) or 0

        last_round_type = ""
        last_round_date = ""
        recency = None

        if isinstance(rounds, list) and rounds:
            rounds_sorted = sorted(rounds, key=lambda r: r.get("announced_on", ""), reverse=True)
            latest = rounds_sorted[0]
            last_round_date = latest.get("announced_on", "")
            title = latest.get("title", "").lower()

            for label in ("series a", "series b", "series c", "series d", "seed", "venture", "pre-seed"):
                if label in title:
                    last_round_type = label.replace(" ", "_")
                    break
            if not last_round_type:
                last_round_type = title.split(" - ")[0].strip() if " - " in title else "unknown"

            if last_round_date:
                try:
                    d = datetime.strptime(last_round_date[:10], "%Y-%m-%d")
                    recency = (datetime.utcnow() - d).days
                except (ValueError, TypeError):
                    pass

        strength = SignalStrength.ABSENT
        if recency is not None:
            is_ab = last_round_type in ("series_a", "series_b")
            if recency <= 180 and is_ab:
                strength = SignalStrength.STRONG
            elif recency <= 180:
                strength = SignalStrength.MODERATE
            elif recency <= 365:
                strength = SignalStrength.WEAK

        return FundingSignal(
            round_type=last_round_type,
            amount_usd=float(funding_total) if funding_total else None,
            date=last_round_date,
            recency_days=recency,
            strength=strength,
            source="crunchbase_odm",
        )

    def get_peers_by_industry(self, industry: str, exclude_name: str = "", limit: int = 10) -> list[dict]:
        """Find peer companies in the same industry."""
        industry_lower = industry.lower()
        peers = []
        exclude = exclude_name.strip().lower()
        for rec in self._data:
            name = (rec.get("name") or "").strip().lower()
            if name == exclude:
                continue
            ind = self._parse_industries(rec).lower()
            if any(term in ind for term in industry_lower.split(",") if len(term.strip()) > 2):
                peers.append({
                    "name": rec.get("name", ""),
                    "description": rec.get("about", ""),
                    "employee_count": self._parse_employees(rec),
                    "industry": self._parse_industries(rec),
                    "funding_total": self._get_funding_total(rec),
                })
                if len(peers) >= limit:
                    break
        return peers

    def _parse_industries(self, rec: dict) -> str:
        raw = rec.get("industries", "")
        parsed = self._parse_json_field(raw)
        if isinstance(parsed, list):
            return ", ".join(item.get("value", "") for item in parsed if isinstance(item, dict))
        return str(raw) if raw else ""

    def _parse_employees(self, rec: dict) -> Optional[int]:
        val = rec.get("num_employees", "")
        if not val:
            return None
        if isinstance(val, int):
            return val
        s = str(val).strip()
        # Handle ranges like "11-50", "51-100", "1-10"
        m = re.match(r"(\d+)\s*[-–]\s*(\d+)", s)
        if m:
            return (int(m.group(1)) + int(m.group(2))) // 2
        # Handle "10000+"
        m = re.match(r"(\d+)\+?", s.replace(",", ""))
        if m:
            return int(m.group(1))
        return None

    def _parse_location(self, rec: dict) -> str:
        parts = []
        loc = rec.get("location", "")
        if loc:
            parsed = self._parse_json_field(loc)
            if isinstance(parsed, dict):
                for k in ("city", "region", "country"):
                    if parsed.get(k):
                        parts.append(str(parsed[k]))
        if not parts:
            cc = rec.get("country_code", "")
            region = rec.get("region", "")
            if region:
                parts.append(str(region))
            if cc:
                parts.append(str(cc))
        return ", ".join(parts)

    def _get_funding_total(self, rec: dict) -> Optional[float]:
        financials = self._parse_json_field(rec.get("financials_highlights", ""))
        if isinstance(financials, dict):
            ft = financials.get("funding_total", {})
            val = ft.get("value_usd", 0) or ft.get("value", 0)
            return float(val) if val else None
        return None

    @staticmethod
    def _parse_json_field(raw) -> any:
        if not raw or raw == "EMPTY":
            return None
        if isinstance(raw, (dict, list)):
            return raw
        try:
            return json.loads(str(raw))
        except (json.JSONDecodeError, TypeError):
            return None
