"""ICP Segment Classifier with abstention."""

from __future__ import annotations
import json
import logging
from pathlib import Path

from agent.models import ICPClassification, ICPSegment, Prospect
from config.settings import settings

logger = logging.getLogger(__name__)

ABSTENTION_THRESHOLD = 0.6


def classify_prospect(prospect: Prospect) -> ICPClassification:
    """Rule-based ICP classification with confidence scoring.

    Priority per official ICP definition:
    1. Layoff + funding → Segment 2
    2. New CTO/VP Eng in 90 days → Segment 3
    3. Specialized capability + AI maturity >= 2 → Segment 4
    4. Fresh funding in 180 days → Segment 1
    5. Otherwise → abstain
    """
    brief = prospect.signal_brief
    if not brief:
        return ICPClassification(
            segment=ICPSegment.UNCLASSIFIED,
            confidence=0.0,
            reasoning="No signal brief available — enrichment not run.",
        )

    scores: dict[ICPSegment, float] = {
        ICPSegment.SEGMENT_1: 0.0,
        ICPSegment.SEGMENT_2: 0.0,
        ICPSegment.SEGMENT_3: 0.0,
        ICPSegment.SEGMENT_4: 0.0,
    }
    reasons: dict[ICPSegment, list[str]] = {s: [] for s in scores}

    emp = prospect.employee_count or 0
    bw = brief.buying_window_signals
    has_layoff = bw.layoff_event.detected
    has_funding = bw.funding_event.detected
    has_leadership = bw.leadership_change.detected

    # --- Classification rule 1: Layoff + funding → Segment 2 ---
    if has_layoff and has_funding:
        scores[ICPSegment.SEGMENT_2] = 0.85
        reasons[ICPSegment.SEGMENT_2].append("Layoff + funding detected — cost pressure dominates")

    # --- Segment 3: Leadership Transition ---
    if has_leadership:
        role = bw.leadership_change.role or ""
        if role in ("cto", "vp_engineering", "cio", "chief_data_officer", "head_of_ai"):
            scores[ICPSegment.SEGMENT_3] = 0.85
            reasons[ICPSegment.SEGMENT_3].append(
                f"New {role} detected: {bw.leadership_change.new_leader_name or 'unknown'}"
            )
        else:
            scores[ICPSegment.SEGMENT_3] = 0.5
            reasons[ICPSegment.SEGMENT_3].append(f"Leadership change detected but role={role}")

    # Disqualify Segment 3 if headcount < 50
    if emp > 0 and emp < 50:
        scores[ICPSegment.SEGMENT_3] = 0.0
        reasons[ICPSegment.SEGMENT_3].append(f"BLOCKED: headcount {emp} < 50")

    # --- Segment 4: Specialized Capability Gap ---
    # HARD GATE: AI maturity must be >= 2
    if brief.ai_maturity.score >= 2:
        gap_score = 0.3 * brief.ai_maturity.confidence
        if brief.bench_to_brief_match.bench_available:
            gap_score += 0.4
            reasons[ICPSegment.SEGMENT_4].append("Bench matches prospect stack")
        if brief.hiring_velocity.open_roles_today > 0:
            gap_score += 0.2
            reasons[ICPSegment.SEGMENT_4].append(
                f"{brief.hiring_velocity.open_roles_today} open roles detected"
            )
        scores[ICPSegment.SEGMENT_4] = min(gap_score, 0.95)
        reasons[ICPSegment.SEGMENT_4].append(
            f"AI maturity {brief.ai_maturity.score}/3 (confidence {brief.ai_maturity.confidence:.2f})"
        )
    else:
        reasons[ICPSegment.SEGMENT_4].append(
            f"BLOCKED: AI maturity {brief.ai_maturity.score}/3 < 2"
        )

    # --- Segment 1: Recently Funded ---
    # HARD RULE: post-layoff companies are NEVER Segment 1
    if has_layoff:
        reasons[ICPSegment.SEGMENT_1].append("BLOCKED: recent layoff detected")
    elif has_funding:
        stage = bw.funding_event.stage or ""
        amount = bw.funding_event.amount_usd or 0
        base = 0.7
        if stage in ("series_a", "series_b"):
            if 5_000_000 <= amount <= 30_000_000:
                base = 0.9
                reasons[ICPSegment.SEGMENT_1].append(
                    f"${amount/1e6:.0f}M {stage} detected"
                )
        if 15 <= emp <= 80:
            base += 0.05
            reasons[ICPSegment.SEGMENT_1].append(f"Employee count {emp} in ICP range")
        if brief.hiring_velocity.open_roles_today >= 5:
            base += 0.05
            reasons[ICPSegment.SEGMENT_1].append(
                f"{brief.hiring_velocity.open_roles_today} open engineering roles (>=5 required)"
            )
        scores[ICPSegment.SEGMENT_1] = min(base, 0.95)

    # --- Segment 2: Restructuring ---
    if has_layoff and not (has_layoff and has_funding):
        pct = bw.layoff_event.percentage_cut or 0
        if pct > 40:
            reasons[ICPSegment.SEGMENT_2].append(f"BLOCKED: layoff {pct}% > 40%")
        else:
            base = 0.7
            if 200 <= emp <= 2000:
                base += 0.1
                reasons[ICPSegment.SEGMENT_2].append(f"Employee count {emp} in mid-market range")
            if brief.hiring_velocity.open_roles_today >= 3:
                base += 0.1
                reasons[ICPSegment.SEGMENT_2].append("Still hiring — maintaining output")
            scores[ICPSegment.SEGMENT_2] = min(base, 0.95)

    # Pick winner by priority: Seg2(layoff+funding) > Seg3 > Seg4 > Seg1 > Seg2
    priority = [
        ICPSegment.SEGMENT_3,
        ICPSegment.SEGMENT_4,
        ICPSegment.SEGMENT_1,
        ICPSegment.SEGMENT_2,
    ]

    # Rule 1 override: layoff + funding → always Segment 2
    if has_layoff and has_funding and scores[ICPSegment.SEGMENT_2] > 0:
        best_segment = ICPSegment.SEGMENT_2
        best_score = scores[ICPSegment.SEGMENT_2]
    else:
        best_segment = ICPSegment.UNCLASSIFIED
        best_score = 0.0
        for seg in priority:
            if scores[seg] > best_score:
                best_segment = seg
                best_score = scores[seg]

    second_segment = None
    for seg in priority:
        if seg != best_segment and scores[seg] > 0:
            second_segment = seg
            break

    # Abstention
    if best_score < ABSTENTION_THRESHOLD:
        return ICPClassification(
            segment=ICPSegment.ABSTAIN,
            confidence=best_score,
            reasoning=f"Below confidence threshold ({best_score:.2f} < {ABSTENTION_THRESHOLD}). "
                      f"Best candidate: {best_segment.value}. "
                      + "; ".join(reasons.get(best_segment, [])),
            secondary_segment=second_segment,
            bench_match=brief.bench_to_brief_match.bench_available,
        )

    return ICPClassification(
        segment=best_segment,
        confidence=best_score,
        reasoning="; ".join(reasons.get(best_segment, [])),
        secondary_segment=second_segment,
        bench_match=brief.bench_to_brief_match.bench_available,
        bench_match_detail=_get_bench_match_detail(brief.tech_stack),
    )


def _get_bench_match_detail(tech_stack: list[str]) -> str:
    bench_path = Path(settings.seed_data_path) / "bench_summary.json"
    if not bench_path.exists():
        return ""
    bench = json.loads(bench_path.read_text())
    matches = []
    for stack_name, info in bench.get("stacks", {}).items():
        if any(stack_name in s.lower() for s in tech_stack):
            matches.append(f"{stack_name}: {info['available_engineers']} available")
    return "; ".join(matches) if matches else "No direct stack match"
