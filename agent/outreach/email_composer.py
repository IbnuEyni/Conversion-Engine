"""Email composer — generates signal-grounded outreach emails."""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional

from agent.models import Prospect, ICPSegment, SignalStrength
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
        f = brief.funding
        if f.strength != SignalStrength.ABSENT:
            lines.append(f"Funding: {f.round_type} ${f.amount_usd/1e6:.1f}M, {f.recency_days}d ago [{f.strength.value}]")
        j = brief.job_posts
        if j.strength != SignalStrength.ABSENT:
            lines.append(f"Jobs: {j.engineering_roles} eng roles, {j.ai_ml_roles} AI/ML, velocity {j.velocity_60d}% [{j.strength.value}]")
        l = brief.layoffs
        if l.occurred:
            lines.append(f"Layoff: {l.headcount} people, {l.recency_days}d ago [{l.strength.value}]")
        ld = brief.leadership
        if ld.new_leader:
            lines.append(f"Leadership: New {ld.title} ({ld.name}), {ld.recency_days}d ago [{ld.strength.value}]")
        ai = brief.ai_maturity
        lines.append(f"AI Maturity: {ai.score}/3 (confidence {ai.confidence:.2f})")
        if ai.justification:
            lines.append(f"  Justification: {'; '.join(ai.justification[:3])}")
        return "\n".join(lines) if lines else "Limited signal data"

    def _format_bench_info(self, brief) -> str:
        if not self._bench_summary:
            return "Bench data not loaded"
        by_stack = self._bench_summary.get("by_stack", {})
        lines = [f"Total available: {self._bench_summary.get('total_available', 0)}"]
        for stack, info in by_stack.items():
            lines.append(f"  {stack}: {info['available']} ({', '.join(f'{k}={v}' for k, v in info.get('levels', {}).items())})")
        return "\n".join(lines)

    def _select_case_study(self, classification) -> str:
        if not classification or not self._case_studies:
            return "No relevant case study"
        seg = classification.segment
        # Return the section of case studies most relevant to the segment
        if seg == ICPSegment.RECENTLY_FUNDED:
            return "Case Study 1: Series B Fintech — 6 engineers onboarded in 3 weeks, fraud pipeline shipped in 4 months"
        elif seg == ICPSegment.RESTRUCTURING:
            return "Case Study 2: Mid-Market SaaS — 10 engineers, 47% cost reduction, zero velocity drop"
        elif seg == ICPSegment.CAPABILITY_GAP:
            return "Case Study 3: Series C AI Company — ML platform migration in 14 weeks, 62% runtime reduction"
        return "No segment-specific case study"
