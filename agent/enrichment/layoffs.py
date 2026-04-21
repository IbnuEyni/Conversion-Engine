"""Layoffs.fyi signal checker.

CSV schema: company, location, industry, total_laid_off,
            percentage_laid_off, date, stage, country, funds_raised_millions
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

from agent.models import LayoffSignal, SignalStrength
from config.settings import settings


class LayoffsChecker:
    def __init__(self):
        self._records: list[dict] = []
        self._index: dict[str, list[dict]] = {}

    def load(self, path: Optional[str] = None):
        p = Path(path or settings.layoffs_data_path)
        if not p.exists():
            return
        with open(p, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                self._records.append(row)
                name = (row.get("company") or "").strip().lower()
                if name:
                    self._index.setdefault(name, []).append(row)

    @property
    def count(self) -> int:
        return len(self._records)

    def check(self, company_name: str) -> LayoffSignal:
        key = company_name.strip().lower()
        matches = self._index.get(key)
        if not matches:
            for k, v in self._index.items():
                if key in k or k in key:
                    matches = v
                    break
        if not matches:
            return LayoffSignal(strength=SignalStrength.ABSENT)

        best = None
        best_recency = 99999
        for rec in matches:
            date_str = (rec.get("date") or "").strip()
            recency = self._parse_recency(date_str)
            if recency is not None and recency < best_recency:
                best_recency = recency
                best = rec

        if best is None:
            best = matches[0]
            best_recency = None

        headcount = self._safe_int(best.get("total_laid_off"))
        pct = self._safe_float(best.get("percentage_laid_off"))

        strength = SignalStrength.ABSENT
        if best_recency is not None:
            if best_recency <= 120:
                strength = SignalStrength.STRONG
            elif best_recency <= 240:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

        return LayoffSignal(
            occurred=True,
            date=best.get("date", ""),
            headcount=headcount,
            percentage=pct,
            recency_days=best_recency,
            strength=strength,
            source="layoffs_fyi",
        )

    @staticmethod
    def _parse_recency(date_str: str) -> Optional[int]:
        if not date_str:
            return None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%d/%m/%Y"):
            try:
                d = datetime.strptime(date_str.strip(), fmt)
                return (datetime.utcnow() - d).days
            except ValueError:
                continue
        return None

    @staticmethod
    def _safe_int(val) -> Optional[int]:
        if not val:
            return None
        try:
            return int(str(val).replace(",", "").strip())
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_float(val) -> Optional[float]:
        if not val:
            return None
        try:
            return float(str(val).replace("%", "").strip())
        except (ValueError, TypeError):
            return None
