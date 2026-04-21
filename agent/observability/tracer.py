"""Langfuse observability — per-trace cost attribution and evidence graph support.

Every LLM call, enrichment step, outreach action, and conversation turn
gets a trace with:
- trace_id (referenced in evidence_graph.json)
- cost attribution (input/output tokens → USD)
- latency (wall clock)
- metadata (prospect_id, company, segment, etc.)

Usage:
    from agent.observability.tracer import tracer, traced_llm_call

    # Wrap an LLM call
    result = traced_llm_call(messages, prospect_id="p-001", step="ai_maturity")

    # Manual trace for non-LLM operations
    with tracer.span("enrichment", prospect_id="p-001") as span:
        ...do work...
        span.end(output={"signal": "funding"}, metadata={"strength": "strong"})
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from config.settings import settings

logger = logging.getLogger(__name__)

# Approximate cost per 1M tokens (OpenRouter pricing)
MODEL_COSTS = {
    "qwen/qwen3-235b-a22b": {"input": 0.20, "output": 0.60},
    "anthropic/claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "deepseek/deepseek-chat-v3-0324": {"input": 0.14, "output": 0.28},
}
DEFAULT_COST = {"input": 0.50, "output": 1.50}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = MODEL_COSTS.get(model, DEFAULT_COST)
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


class Tracer:
    """Singleton Langfuse tracer with local JSONL fallback."""

    def __init__(self):
        self._langfuse = None
        self._trace_log_path = Path("eval/trace_log.jsonl")
        self._trace_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._total_cost = 0.0
        self._total_tokens = 0
        self._call_count = 0

    @property
    def langfuse(self):
        if self._langfuse is None:
            try:
                from langfuse import Langfuse
                lf = Langfuse()
                if lf.auth_check():
                    self._langfuse = lf
                    logger.info("Langfuse connected")
                else:
                    logger.warning("Langfuse auth failed — using local trace log only")
            except Exception as e:
                logger.warning(f"Langfuse init failed: {e} — using local trace log only")
        return self._langfuse

    @property
    def is_connected(self) -> bool:
        return self.langfuse is not None

    @property
    def stats(self) -> dict:
        return {
            "total_cost_usd": round(self._total_cost, 6),
            "total_tokens": self._total_tokens,
            "call_count": self._call_count,
            "langfuse_connected": self.is_connected,
        }

    # ── LLM Call Tracing ─────────────────────────────────────

    def trace_llm_call(
        self,
        messages: list[dict],
        response: dict,
        step: str,
        prospect_id: str = "",
        metadata: Optional[dict] = None,
    ) -> str:
        """Trace an LLM call to Langfuse + local JSONL."""
        model = response.get("model", settings.dev_model)
        input_tokens = response.get("prompt_tokens", 0)
        output_tokens = response.get("completion_tokens", 0)
        latency = response.get("latency_s", 0)
        cost = _estimate_cost(model, input_tokens, output_tokens)

        self._total_cost += cost
        self._total_tokens += input_tokens + output_tokens
        self._call_count += 1

        trace_id = f"llm_{step}_{prospect_id}_{self._call_count}"
        now = datetime.now(timezone.utc).isoformat()

        # Local JSONL log (always written)
        record = {
            "trace_id": trace_id,
            "type": "llm_call",
            "step": step,
            "prospect_id": prospect_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": round(cost, 6),
            "latency_s": round(latency, 3),
            "timestamp": now,
            "metadata": metadata or {},
        }
        self._write_local(record)

        # Langfuse
        if self.is_connected:
            try:
                self.langfuse.create_event(
                    name=f"llm_{step}",
                    input=messages[-1].get("content", "")[:500] if messages else "",
                    output=response.get("content", "")[:500],
                    metadata={
                        "trace_id": trace_id,
                        "prospect_id": prospect_id,
                        "model": model,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cost_usd": round(cost, 6),
                        "latency_s": round(latency, 3),
                        **(metadata or {}),
                    },
                )
            except Exception as e:
                logger.warning(f"Langfuse event failed: {e}")

        return trace_id

    # ── Pipeline Step Tracing ────────────────────────────────

    @contextmanager
    def span(self, step: str, prospect_id: str = "", metadata: Optional[dict] = None):
        """Context manager for tracing a pipeline step."""
        start = time.time()
        trace_id = f"span_{step}_{prospect_id}_{self._call_count}"
        ctx = {"trace_id": trace_id, "output": None, "metadata": metadata or {}}

        try:
            yield ctx
        finally:
            elapsed = time.time() - start
            record = {
                "trace_id": trace_id,
                "type": "span",
                "step": step,
                "prospect_id": prospect_id,
                "latency_s": round(elapsed, 3),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "output": ctx.get("output"),
                "metadata": ctx.get("metadata", {}),
            }
            self._write_local(record)

            if self.is_connected:
                try:
                    self.langfuse.create_event(
                        name=f"span_{step}",
                        output=str(ctx.get("output", ""))[:500],
                        metadata={
                            "trace_id": trace_id,
                            "prospect_id": prospect_id,
                            "latency_s": round(elapsed, 3),
                            **(ctx.get("metadata", {})),
                        },
                    )
                except Exception as e:
                    logger.warning(f"Langfuse span event failed: {e}")

    # ── Outbound Action Tracing ──────────────────────────────

    def trace_outbound(
        self,
        action: str,
        prospect_id: str,
        channel: str,
        content_preview: str = "",
        metadata: Optional[dict] = None,
    ) -> str:
        """Trace an outbound action (email, SMS, booking)."""
        trace_id = f"out_{action}_{prospect_id}_{self._call_count}"
        record = {
            "trace_id": trace_id,
            "type": "outbound",
            "action": action,
            "prospect_id": prospect_id,
            "channel": channel,
            "content_preview": content_preview[:200],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        self._write_local(record)

        if self.is_connected:
            try:
                self.langfuse.create_event(
                    name=f"outbound_{action}",
                    output=content_preview[:500],
                    metadata={
                        "trace_id": trace_id,
                        "prospect_id": prospect_id,
                        "channel": channel,
                        **(metadata or {}),
                    },
                )
            except Exception as e:
                logger.warning(f"Langfuse outbound event failed: {e}")

        return trace_id

    # ── Score Logging ────────────────────────────────────────

    def log_score(self, trace_id: str, name: str, value: float, comment: str = ""):
        """Log a score (for tau2-bench results, probe outcomes, etc.)."""
        record = {
            "trace_id": trace_id,
            "type": "score",
            "name": name,
            "value": value,
            "comment": comment,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._write_local(record)

        if self.is_connected:
            try:
                self.langfuse.create_score(name=name, value=value, comment=comment)
            except Exception as e:
                logger.warning(f"Langfuse score failed: {e}")

    # ── Flush ────────────────────────────────────────────────

    def flush(self):
        if self.is_connected:
            try:
                self.langfuse.flush()
            except Exception:
                pass

    # ── Local JSONL ──────────────────────────────────────────

    def _write_local(self, record: dict):
        with open(self._trace_log_path, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")


# Module singleton
tracer = Tracer()
