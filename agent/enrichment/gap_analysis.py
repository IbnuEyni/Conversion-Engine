"""Competitor gap analysis — per competitor_gap_brief.schema.json."""

from __future__ import annotations
from datetime import datetime
from agent.models import (
    CompetitorGapBrief, CompetitorEntry, GapFinding, PeerEvidence,
    GapQualitySelfCheck, HiringSignalBrief,
)
from agent.llm_client import get_llm


GAP_ANALYSIS_PROMPT = """You are a competitive intelligence analyst for B2B technology companies.

Given a prospect and peer companies, produce a competitor gap brief per the schema below.

## Prospect
Company: {company_name}
Domain: {domain}
Industry: {industry}
AI Maturity Score: {ai_maturity}/3
Tech Stack: {tech_stack}
Description: {description}

## Peer Companies
{peer_data}

## Output (JSON) — must conform to competitor_gap_brief.schema.json
{{
  "prospect_sector": "sector name",
  "prospect_sub_niche": "optional finer niche",
  "prospect_ai_maturity_score": {ai_maturity},
  "sector_top_quartile_benchmark": 0.0,
  "competitors_analyzed": [
    {{
      "name": "company name",
      "domain": "domain.com",
      "ai_maturity_score": 0,
      "ai_maturity_justification": ["one line per signal"],
      "headcount_band": "15_to_80|80_to_200|200_to_500|500_to_2000|2000_plus",
      "top_quartile": false,
      "sources_checked": ["url"]
    }}
  ],
  "gap_findings": [
    {{
      "practice": "specific verifiable practice",
      "peer_evidence": [
        {{"competitor_name": "name", "evidence": "specific evidence", "source_url": "url"}}
      ],
      "prospect_state": "what prospect shows or does not show",
      "confidence": "high|medium|low",
      "segment_relevance": ["segment_1_series_a_b"]
    }}
  ],
  "suggested_pitch_shift": "brief note for outreach composer",
  "gap_quality_self_check": {{
    "all_peer_evidence_has_source_url": true,
    "at_least_one_gap_high_confidence": true,
    "prospect_silent_but_sophisticated_risk": false
  }}
}}

IMPORTANT:
- Quality is graded on specificity. "they use AI" is useless; "three peers have opened named MLOps-platform-engineer roles in the last 60 days" is valuable.
- Frame gaps as research findings, not judgments.
- Each gap finding needs at least 2 peer evidence items.
- Be honest about confidence levels."""


def analyze_competitor_gap(
    prospect_brief: HiringSignalBrief,
    peer_companies: list[dict],
    industry: str = "",
    description: str = "",
) -> CompetitorGapBrief:
    if not peer_companies:
        return CompetitorGapBrief(
            prospect_domain=prospect_brief.prospect_domain,
            prospect_sector=industry,
            prospect_ai_maturity_score=prospect_brief.ai_maturity.score,
        )

    peer_lines = []
    for p in peer_companies[:10]:
        peer_lines.append(
            f"- {p.get('name', 'Unknown')}: {p.get('description', 'N/A')}, "
            f"employees: {p.get('employee_count', '?')}, "
            f"funding: {p.get('funding', '?')}, "
            f"stack: {p.get('tech_stack', '?')}"
        )

    prompt = GAP_ANALYSIS_PROMPT.format(
        company_name=prospect_brief.prospect_name,
        domain=prospect_brief.prospect_domain,
        industry=industry or "Technology",
        ai_maturity=prospect_brief.ai_maturity.score,
        tech_stack=", ".join(prospect_brief.tech_stack) if prospect_brief.tech_stack else "Unknown",
        description=description or "No description",
        peer_data="\n".join(peer_lines) if peer_lines else "No peer data available",
    )

    llm = get_llm("dev")
    result = llm.complete_json([
        {"role": "system", "content": "You are a precise analyst. Output valid JSON only."},
        {"role": "user", "content": prompt},
    ], max_tokens=2048)

    parsed = result["parsed"]

    competitors = [
        CompetitorEntry(**c) for c in parsed.get("competitors_analyzed", [])
    ]

    gap_findings = []
    for gf in parsed.get("gap_findings", []):
        peer_ev = [PeerEvidence(**pe) for pe in gf.get("peer_evidence", [])]
        gap_findings.append(GapFinding(
            practice=gf.get("practice", ""),
            peer_evidence=peer_ev,
            prospect_state=gf.get("prospect_state", ""),
            confidence=gf.get("confidence", "medium"),
            segment_relevance=gf.get("segment_relevance", []),
        ))

    self_check_raw = parsed.get("gap_quality_self_check", {})
    self_check = GapQualitySelfCheck(
        all_peer_evidence_has_source_url=self_check_raw.get("all_peer_evidence_has_source_url", False),
        at_least_one_gap_high_confidence=self_check_raw.get("at_least_one_gap_high_confidence", False),
        prospect_silent_but_sophisticated_risk=self_check_raw.get("prospect_silent_but_sophisticated_risk", False),
    )

    return CompetitorGapBrief(
        prospect_domain=prospect_brief.prospect_domain,
        prospect_sector=parsed.get("prospect_sector", industry),
        prospect_sub_niche=parsed.get("prospect_sub_niche"),
        generated_at=datetime.utcnow().isoformat() + "Z",
        prospect_ai_maturity_score=prospect_brief.ai_maturity.score,
        sector_top_quartile_benchmark=parsed.get("sector_top_quartile_benchmark", 0.0),
        competitors_analyzed=competitors,
        gap_findings=gap_findings,
        suggested_pitch_shift=parsed.get("suggested_pitch_shift", ""),
        gap_quality_self_check=self_check,
    )
