"""ICP Segment Classifier with abstention."""

from __future__ import annotations
import json
import logging
from pathlib import Path

from agent.models import (
    ICPClassification, ICPSegment, Prospect, SignalStrength,
)
from config.settings import settings

logger = logging.getLogger(__name__)

ABSTENTION_THRESHOLD = 0.6


def classify_prospect(prospect: Prospect) -> ICPClassification:
    """Rule-based ICP classification with confidence scoring.

    Priority: Segment 3 > Segment 4 > Segment 1 > Segment 2
    Hard rules enforced before scoring.
    """
    brief = prospect.signal_brief
    if not brief:
        return ICPClassification(
            segment=ICPSegment.UNCLASSIFIED,
            confidence=0.0,
            reasoning="No signal brief available — enrichment not run.",
        )

    scores: dict[ICPSegment, float] = {
        ICPSegment.RECENTLY_FUNDED: 0.0,
        ICPSegment.RESTRUCTURING: 0.0,
        ICPSegment.LEADERSHIP_TRANSITION: 0.0,
        ICPSegment.CAPABILITY_GAP: 0.0,
    }
    reasons: dict[ICPSegment, list[str]] = {s: [] for s in scores}

    emp = prospect.employee_count or 0
    has_layoff = brief.layoffs.occurred and brief.layoffs.strength in (
        SignalStrength.STRONG, SignalStrength.MODERATE
    )

    # --- Segment 3: Leadership Transition ---
    if brief.leadership.new_leader and brief.leadership.strength != SignalStrength.ABSENT:
        recency = brief.leadership.recency_days or 999
        if recency <= 90:
            scores[ICPSegment.LEADERSHIP_TRANSITION] = 0.85
            reasons[ICPSegment.LEADERSHIP_TRANSITION].append(
                f"New {brief.leadership.title} appointed {recency} days ago"
            )
        elif recency <= 180:
            scores[ICPSegment.LEADERSHIP_TRANSITION] = 0.5
            reasons[ICPSegment.LEADERSHIP_TRANSITION].append(
                f"Leadership change {recency} days ago (outside 90-day window)"
            )

    # --- Segment 4: Capability Gap ---
    # HARD GATE: AI maturity must be >= 2
    if brief.ai_maturity.score >= 2:
        gap_score = 0.3 * brief.ai_maturity.confidence
        if _bench_matches_stack(brief.tech_stack):
            gap_score += 0.4
            reasons[ICPSegment.CAPABILITY_GAP].append("Bench matches prospect stack")
        if brief.job_posts.ai_ml_roles > 0:
            gap_score += 0.2
            reasons[ICPSegment.CAPABILITY_GAP].append(
                f"{brief.job_posts.ai_ml_roles} AI/ML roles open"
            )
        scores[ICPSegment.CAPABILITY_GAP] = min(gap_score, 0.95)
        reasons[ICPSegment.CAPABILITY_GAP].append(
            f"AI maturity {brief.ai_maturity.score}/3 (confidence {brief.ai_maturity.confidence:.2f})"
        )
    else:
        reasons[ICPSegment.CAPABILITY_GAP].append(
            f"BLOCKED: AI maturity {brief.ai_maturity.score}/3 < 2"
        )

    # --- Segment 1: Recently Funded ---
    # HARD RULE: post-layoff companies are NEVER Segment 1
    if has_layoff:
        reasons[ICPSegment.RECENTLY_FUNDED].append("BLOCKED: recent layoff detected")
    else:
        funding = brief.funding
        if funding.strength == SignalStrength.STRONG:
            base = 0.7
            if funding.round_type and "series" in funding.round_type.lower():
                if funding.amount_usd and 5_000_000 <= funding.amount_usd <= 30_000_000:
                    base = 0.9
                    reasons[ICPSegment.RECENTLY_FUNDED].append(
                        f"${funding.amount_usd/1e6:.0f}M {funding.round_type} in last 180 days"
                    )
            if 15 <= emp <= 80:
                base += 0.05
                reasons[ICPSegment.RECENTLY_FUNDED].append(f"Employee count {emp} in ICP range")
            if brief.job_posts.strength in (SignalStrength.STRONG, SignalStrength.MODERATE):
                base += 0.05
                reasons[ICPSegment.RECENTLY_FUNDED].append("Active hiring signal")
            scores[ICPSegment.RECENTLY_FUNDED] = min(base, 0.95)
        elif funding.strength == SignalStrength.MODERATE:
            scores[ICPSegment.RECENTLY_FUNDED] = 0.5
            reasons[ICPSegment.RECENTLY_FUNDED].append("Recent funding but not Series A/B")

    # --- Segment 2: Restructuring ---
    if has_layoff:
        base = 0.6
        if brief.layoffs.strength == SignalStrength.STRONG:
            base = 0.75
            reasons[ICPSegment.RESTRUCTURING].append(
                f"Layoff {brief.layoffs.recency_days} days ago"
            )
        if 200 <= emp <= 2000:
            base += 0.1
            reasons[ICPSegment.RESTRUCTURING].append(f"Employee count {emp} in mid-market range")
        if brief.job_posts.strength != SignalStrength.ABSENT:
            base += 0.1
            reasons[ICPSegment.RESTRUCTURING].append("Still hiring — maintaining output")
        scores[ICPSegment.RESTRUCTURING] = min(base, 0.95)

    # Pick winner by priority (Seg3 > Seg4 > Seg1 > Seg2) with score threshold
    priority = [
        ICPSegment.LEADERSHIP_TRANSITION,
        ICPSegment.CAPABILITY_GAP,
        ICPSegment.RECENTLY_FUNDED,
        ICPSegment.RESTRUCTURING,
    ]

    best_segment = ICPSegment.UNCLASSIFIED
    best_score = 0.0
    second_segment = None

    for seg in priority:
        if scores[seg] > best_score:
            second_segment = best_segment if best_score > 0 else None
            best_segment = seg
            best_score = scores[seg]

    # Abstention: if confidence below threshold, classify as unclassified
    if best_score < ABSTENTION_THRESHOLD:
        return ICPClassification(
            segment=ICPSegment.UNCLASSIFIED,
            confidence=best_score,
            reasoning=f"Below confidence threshold ({best_score:.2f} < {ABSTENTION_THRESHOLD}). "
                      f"Best candidate: {best_segment.value}. "
                      + "; ".join(reasons.get(best_segment, [])),
            secondary_segment=second_segment,
            bench_match=_bench_matches_stack(brief.tech_stack),
        )

    return ICPClassification(
        segment=best_segment,
        confidence=best_score,
        reasoning="; ".join(reasons.get(best_segment, [])),
        secondary_segment=second_segment,
        bench_match=_bench_matches_stack(brief.tech_stack),
        bench_match_detail=_get_bench_match_detail(brief.tech_stack),
    )


def _bench_matches_stack(tech_stack: list[str]) -> bool:
    """Check if prospect's tech stack matches Tenacious bench."""
    bench_path = Path(settings.seed_data_path) / "bench_summary.json"
    if not bench_path.exists():
        return False
    bench = json.loads(bench_path.read_text())
    bench_stacks = set(bench.get("by_stack", {}).keys())
    # normalize
    stack_lower = {s.lower().replace(" ", "_") for s in tech_stack}
    return bool(bench_stacks & stack_lower)


def _get_bench_match_detail(tech_stack: list[str]) -> str:
    bench_path = Path(settings.seed_data_path) / "bench_summary.json"
    if not bench_path.exists():
        return ""
    bench = json.loads(bench_path.read_text())
    matches = []
    for stack_name, info in bench.get("by_stack", {}).items():
        if any(stack_name in s.lower() for s in tech_stack):
            matches.append(f"{stack_name}: {info['available']} available")
    return "; ".join(matches) if matches else "No direct stack match"
