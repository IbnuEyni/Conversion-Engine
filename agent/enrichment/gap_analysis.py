"""Competitor gap analysis — compares prospect against top-quartile peers."""

from __future__ import annotations
import json
from agent.models import CompetitorGapBrief, CompetitorGapEntry, HiringSignalBrief
from agent.llm_client import get_llm


GAP_ANALYSIS_PROMPT = """You are a competitive intelligence analyst for B2B technology companies.

Given a prospect company and a list of peer companies in the same sector, analyze the prospect's position relative to the top quartile.

## Prospect
Company: {company_name}
Industry: {industry}
Employee Count: {employee_count}
AI Maturity Score: {ai_maturity}/3 (confidence: {ai_confidence})
Tech Stack: {tech_stack}
Description: {description}

## Peer Companies (same sector, similar stage)
{peer_data}

## Task
1. Identify where the prospect sits relative to the top quartile of peers
2. Extract 2-3 specific practices the top quartile shows public signal for that the prospect does NOT
3. Frame gaps as research findings, not judgments
4. Be honest about what you can and cannot determine from public data

## Output (JSON)
{{
  "prospect_position": "below median" | "median" | "above median" | "top quartile",
  "sector": "the sector name",
  "top_quartile_practices": ["practice 1", "practice 2", "practice 3"],
  "specific_gaps": ["gap 1 — framed as observation not judgment", "gap 2", "gap 3"],
  "competitors": [
    {{"competitor_name": "name", "ai_maturity": 0-3, "key_practices": ["practice"], "source": "signal source"}}
  ]
}}

IMPORTANT: Frame gaps respectfully. A CTO who is behind knows they're behind. Present as "what the top quartile is doing" not "what you're missing"."""


def analyze_competitor_gap(
    prospect_brief: HiringSignalBrief,
    peer_companies: list[dict],
    industry: str = "",
    description: str = "",
) -> CompetitorGapBrief:
    if not peer_companies:
        return CompetitorGapBrief(
            prospect_position="insufficient data",
            sector=industry,
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
        company_name=prospect_brief.company_name,
        industry=industry or "Technology",
        employee_count=prospect_brief.job_posts.total_open_roles if prospect_brief.job_posts else "Unknown",
        ai_maturity=prospect_brief.ai_maturity.score,
        ai_confidence=f"{prospect_brief.ai_maturity.confidence:.2f}",
        tech_stack=", ".join(prospect_brief.tech_stack) if prospect_brief.tech_stack else "Unknown",
        description=description or "No description",
        peer_data="\n".join(peer_lines) if peer_lines else "No peer data available",
    )

    llm = get_llm("dev")
    result = llm.complete_json([
        {"role": "system", "content": "You are a precise analyst. Output valid JSON only."},
        {"role": "user", "content": prompt},
    ], max_tokens=1536)

    parsed = result["parsed"]
    competitors = [
        CompetitorGapEntry(**c) for c in parsed.get("competitors", [])
    ]

    return CompetitorGapBrief(
        prospect_position=parsed.get("prospect_position", "unknown"),
        sector=parsed.get("sector", industry),
        top_quartile_practices=parsed.get("top_quartile_practices", []),
        specific_gaps=parsed.get("specific_gaps", []),
        competitors=competitors,
    )
