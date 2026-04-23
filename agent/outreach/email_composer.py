"""Email composer — generates signal-grounded outreach emails."""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional

from agent.models import Prospect, ICPSegment
from agent.llm_client import get_llm
from config.settings import settings

logger = logging.getLogger(__name__)

COMPOSE_PROMPT = """You are writing a cold outreach email for Tenacious Consulting & Outsourcing.

## Style Rules (MANDATORY)
{style_guide}

## Prospect Data
Company: {company_name}
Contact: {contact_name} ({contact_title})
Segment: {segment}
Segment Confidence: {confidence}

## Hiring Signal Brief
{signal_brief}

## Competitor Gap Brief
{gap_brief}

## Bench Availability
{bench_info}

## Case Study (if relevant)
{case_study}

## Instructions
1. Open with a specific, verifiable signal about their company (from the hiring signal brief)
2. If gap brief is available and segment is appropriate, reference the top-quartile comparison
3. Match pitch angle to their segment
4. If signal confidence is LOW, ask rather than assert
5. End with exactly one CTA — usually "Worth a 30-minute conversation?"
6. Keep to 3 paragraphs max
7. NEVER claim capacity not shown in bench availability
8. NEVER use banned phrases from the style guide
9. Mark all output as draft

## Output (JSON)
{{
  "subject": "email subject line — signal-grounded, no clickbait",
  "body": "the full email body",
  "signal_references": ["list of specific signals referenced in the email"],
  "confidence_level": "high" | "moderate" | "low",
  "draft": true
}}"""


class EmailComposer:
    def __init__(self):
        self._style_guide = ""
        self._bench_summary = {}
        self._case_studies = ""

    def load_seed_data(self):
        seed = Path(settings.seed_data_path)
        sg = seed / "style_guide.md"
        if sg.exists():
            self._style_guide = sg.read_text()
        bs = seed / "bench_summary.json"
        if bs.exists():
            self._bench_summary = json.loads(bs.read_text())
        cs = seed / "case_studies.md"
        if cs.exists():
            self._case_studies = cs.read_text()

    def compose(self, prospect: Prospect, sequence_step: int = 1) -> dict:
        """Compose an outreach email for a prospect."""
        self.load_seed_data()

        brief = prospect.signal_brief
        gap = prospect.gap_brief
        classification = prospect.classification

        # Build signal brief summary
        signal_summary = "No signal data available"
        if brief:
            signal_summary = self._format_signal_brief(brief)

        # Build gap brief summary
        gap_summary = "No competitor gap data available"
        if gap and gap.specific_gaps:
            gap_summary = (
                f"Position: {gap.prospect_position}\n"
                f"Top quartile practices: {', '.join(gap.top_quartile_practices)}\n"
                f"Specific gaps: {', '.join(gap.specific_gaps)}"
            )

        # Build bench info
        bench_info = self._format_bench_info(brief)

        # Select relevant case study
        case_study = self._select_case_study(classification)

        segment_name = classification.segment.value if classification else "unclassified"
        confidence = classification.confidence if classification else 0.0

        prompt = COMPOSE_PROMPT.format(
            style_guide=self._style_guide[:2000],
            company_name=prospect.company_name,
            contact_name=prospect.contact_name or "there",
            contact_title=prospect.contact_title or "Engineering Leader",
            segment=segment_name,
            confidence=f"{confidence:.2f}",
            signal_brief=signal_summary,
            gap_brief=gap_summary,
            bench_info=bench_info,
            case_study=case_study,
        )

        llm = get_llm("dev")
        result = llm.complete_json([
            {"role": "system", "content": "You write concise B2B outreach emails. Output valid JSON only."},
            {"role": "user", "content": prompt},
        ], max_tokens=1024)

        email_data = result["parsed"]
        email_data["draft"] = True
        email_data["prospect_id"] = prospect.id
        email_data["sequence_step"] = sequence_step
        email_data["tokens_used"] = result["tokens"]
        email_data["latency_s"] = result["latency_s"]
        return email_data

    def _format_signal_brief(self, brief) -> str:
        lines = []
        bw = brief.buying_window_signals
        if bw.funding_event.detected:
            lines.append(f"Funding: {bw.funding_event.stage} ${bw.funding_event.amount_usd/1e6:.1f}M, closed {bw.funding_event.closed_at}")
        hv = brief.hiring_velocity
        if hv.open_roles_today > 0:
            lines.append(f"Jobs: {hv.open_roles_today} open roles today vs {hv.open_roles_60_days_ago} 60 days ago → {hv.velocity_label.value}")
        if bw.layoff_event.detected:
            lines.append(f"Layoff: {bw.layoff_event.headcount_reduction} people on {bw.layoff_event.date}")
        if bw.leadership_change.detected:
            lines.append(f"Leadership: New {bw.leadership_change.role} ({bw.leadership_change.new_leader_name}), started {bw.leadership_change.started_at}")
        ai = brief.ai_maturity
        lines.append(f"AI Maturity: {ai.score}/3 (confidence {ai.confidence:.2f})")
        if ai.justifications:
            lines.append(f"  Justification: {'; '.join(j.status for j in ai.justifications[:3])}")
        if brief.honesty_flags:
            lines.append(f"Honesty flags: {', '.join(brief.honesty_flags)}")
        return "\n".join(lines) if lines else "Limited signal data"

    def _format_bench_info(self, brief) -> str:
        if not self._bench_summary:
            return "Bench data not loaded"
        stacks = self._bench_summary.get("stacks", {})
        lines = [f"Total available: {self._bench_summary.get('total_engineers_on_bench', 0)}"]
        for stack, info in stacks.items():
            mix = info.get('seniority_mix', {})
            lines.append(f"  {stack}: {info['available_engineers']} ({', '.join(f'{k}={v}' for k, v in mix.items())})")
        return "\n".join(lines)

    def _select_case_study(self, classification) -> str:
        if not classification or not self._case_studies:
            return "No relevant case study"
        seg = classification.segment
        if seg == ICPSegment.SEGMENT_1:
            return 'Case Study 1: Global AdTech platform — dedicated ML team, X% margin improvement on bidding line, ongoing year 2'
        elif seg == ICPSegment.SEGMENT_2:
            return 'Case Study 2: North American loyalty platform — AI configuration layer took partner onboarding from months to days'
        elif seg == ICPSegment.SEGMENT_4:
            return 'Case Study 3: Multi-location fitness franchise — 5-phase sales-automation platform connecting 3 existing tools without migration'
        elif seg == ICPSegment.SEGMENT_3:
            return 'Case Study 1: Global AdTech platform — dedicated ML team embedded in client delivery structure'
        return "No segment-specific case study"
