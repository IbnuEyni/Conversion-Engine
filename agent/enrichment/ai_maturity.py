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
    raw_score = max(0, min(3, int(parsed.get("score", 0))))
    raw_confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))

    # Build per-signal justifications with explicit weights
    justifications = _build_justifications(parsed, job_signal, tech_stack)

    # Silent-company handling: if all signals are absent, score 0 with
    # explicit "no public signal" message — absence of signal is not
    # proof of absence of capability
    all_absent = all(
        "no " in j.status.lower() or "absent" in j.status.lower() or "none" in j.status.lower()
        for j in justifications
    )
    if all_absent and raw_score == 0:
        justifications.append(AIMaturityJustification(
            signal="silent_company_flag",
            status="No public AI signal detected. Score 0 does not prove absence of AI capability — company may be sophisticated but publicly silent (e.g., stealth mode, classified work, or deliberate low profile).",
            weight="high",
            confidence="low",
        ))
        raw_confidence = min(raw_confidence, 0.3)

    return AIMaturityScore(
        score=raw_score,
        confidence=raw_confidence,
        justifications=justifications,
    )


# Six explicit signal categories with documented weights
SIGNAL_WEIGHTS = {
    "ai_adjacent_open_roles": "high",
    "named_ai_ml_leadership": "high",
    "public_github_ai_repos": "medium",
    "executive_ai_commentary": "medium",
    "modern_data_ml_stack": "low",
    "strategic_ai_communications": "low",
}


def _build_justifications(parsed: dict, job_signal, tech_stack) -> list:
    """Build justification list ensuring all 6 weighted signal categories are represented."""
    justifications = []

    # Parse LLM justifications
    for j in parsed.get("justification", []):
        if isinstance(j, str):
            justifications.append(AIMaturityJustification(
                signal="general", status=j, weight="medium", confidence="medium"
            ))
        elif isinstance(j, dict):
            justifications.append(AIMaturityJustification(**j))

    # Parse signal_inputs
    for signal_name, value in parsed.get("signal_inputs", {}).items():
        if not any(jj.signal == signal_name for jj in justifications):
            weight = SIGNAL_WEIGHTS.get(signal_name, "medium")
            justifications.append(AIMaturityJustification(
                signal=signal_name, status=str(value), weight=weight, confidence="medium"
            ))

    # Ensure all 6 categories are present
    existing_signals = {j.signal for j in justifications}
    for signal_name, weight in SIGNAL_WEIGHTS.items():
        if signal_name not in existing_signals:
            status = _default_status(signal_name, job_signal, tech_stack)
            justifications.append(AIMaturityJustification(
                signal=signal_name, status=status, weight=weight, confidence="low"
            ))

    return justifications


def _default_status(signal_name: str, job_signal, tech_stack) -> str:
    """Generate default status for missing signal categories."""
    if signal_name == "ai_adjacent_open_roles":
        if job_signal and getattr(job_signal, 'ai_ml_roles', 0) > 0:
            return f"{job_signal.ai_ml_roles} AI/ML roles detected"
        return "No AI/ML job posts detected in career page data"
    elif signal_name == "named_ai_ml_leadership":
        return "No named AI/ML leadership found in public sources"
    elif signal_name == "public_github_ai_repos":
        return "No public GitHub AI/ML repository activity checked"
    elif signal_name == "executive_ai_commentary":
        return "No recent executive AI commentary found"
    elif signal_name == "modern_data_ml_stack":
        if tech_stack:
            ml_stacks = [s for s in tech_stack if s.lower() in ('pytorch', 'tensorflow', 'ray', 'mlflow', 'databricks', 'snowflake', 'dbt')]
            if ml_stacks:
                return f"ML stack signals: {', '.join(ml_stacks)}"
        return "No modern data/ML stack signals detected"
    elif signal_name == "strategic_ai_communications":
        return "No strategic AI communications found in public materials"
    return "No data available"
