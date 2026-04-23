"""AI Maturity Scorer (0-3) from public signals."""

from __future__ import annotations
import json
from agent.models import AIMaturityScore, AIMaturityJustification, SignalStrength
from agent.llm_client import get_llm

SCORING_PROMPT = """You are an AI maturity analyst. Score a company's AI maturity from 0-3 based on public signals.

## Scoring Scale
- 0: No public signal of AI engagement
- 1: Early signals — a few AI-adjacent roles or executive mentions, no dedicated AI leadership
- 2: Active engagement — dedicated AI/ML roles, named AI leadership, some public AI work
- 3: Mature AI function — active AI team, recent executive commitment, multiple open AI roles, public AI outputs

## Signal Weights
- HIGH: AI-adjacent open roles (ML engineer, applied scientist, LLM engineer, AI PM, data platform engineer) as fraction of total engineering openings
- HIGH: Named AI/ML leadership (Head of AI, VP Data, Chief Scientist)
- MEDIUM: Public GitHub org activity on AI/ML repos
- MEDIUM: Executive commentary naming AI as strategic (last 12 months)
- LOW: Modern data/ML stack signals (dbt, Snowflake, Databricks, W&B, Ray, vLLM)
- LOW: Strategic communications positioning AI as priority

## Company Data
Company: {company_name}
Industry: {industry}
Description: {description}
Employee Count: {employee_count}
Job Post Data: {job_data}
Tech Stack Signals: {tech_stack}
Additional Context: {additional_context}

## Output (JSON)
Return a JSON object with:
- "score": integer 0-3
- "confidence": float 0.0-1.0 (how confident you are in this score given the available evidence)
- "justification": list of strings, one per signal input that contributed to the score
- "signal_inputs": dict mapping signal name to its observed value

Be conservative. If evidence is thin, score lower and set confidence lower. Never over-claim."""


def score_ai_maturity(
    company_name: str,
    industry: str = "",
    description: str = "",
    employee_count: int = 0,
    job_signal=None,
    tech_stack: list[str] | None = None,
    additional_context: str = "",
) -> AIMaturityScore:
    job_data = "No job post data available"
    if job_signal and getattr(job_signal, 'strength', SignalStrength.ABSENT) != SignalStrength.ABSENT:
        job_data = (
            f"Total open roles: {job_signal.total_open_roles}, "
            f"Engineering roles: {job_signal.engineering_roles}, "
            f"AI/ML roles: {job_signal.ai_ml_roles}, "
            f"60-day velocity: {job_signal.velocity_60d}%, "
            f"Top stacks: {', '.join(job_signal.top_stacks)}"
        )

    prompt = SCORING_PROMPT.format(
        company_name=company_name,
        industry=industry or "Unknown",
        description=description or "No description available",
        employee_count=employee_count or "Unknown",
        job_data=job_data,
        tech_stack=", ".join(tech_stack) if tech_stack else "No stack data",
        additional_context=additional_context or "None",
    )

    llm = get_llm("dev")
    result = llm.complete_json([
        {"role": "system", "content": "You are a precise analyst. Output valid JSON only."},
        {"role": "user", "content": prompt},
    ], max_tokens=1024)

    parsed = result["parsed"]
    justifications = []
    for j in parsed.get("justification", []):
        if isinstance(j, str):
            justifications.append(AIMaturityJustification(
                signal="general", status=j, weight="medium", confidence="medium"
            ))
        elif isinstance(j, dict):
            justifications.append(AIMaturityJustification(**j))
    # Also parse signal_inputs into justifications if present
    for signal_name, value in parsed.get("signal_inputs", {}).items():
        if not any(jj.signal == signal_name for jj in justifications):
            justifications.append(AIMaturityJustification(
                signal=signal_name, status=str(value), weight="medium", confidence="medium"
            ))
    return AIMaturityScore(
        score=max(0, min(3, int(parsed.get("score", 0)))),
        confidence=max(0.0, min(1.0, float(parsed.get("confidence", 0.0)))),
        justifications=justifications,
    )
