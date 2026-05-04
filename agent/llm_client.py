"""LLM client via OpenRouter with cost tracking for Langfuse."""

from __future__ import annotations
import json
import re
import time
from typing import Optional
from openai import OpenAI
from config.settings import settings
from agent.observability.tracer import tracer


class LLMClient:
    def __init__(self, mode: str = "dev"):
        self.mode = mode
        self.model = settings.dev_model if mode == "dev" else settings.eval_model
        self.temperature = settings.dev_temperature if mode == "dev" else settings.eval_temperature
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
        )
        self.total_tokens = 0
        self.total_cost = 0.0
        self.call_count = 0
        self._current_step = "unknown"
        self._current_prospect_id = ""

    def complete(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: int = 2048,
        response_format: Optional[dict] = None,
    ) -> dict:
        start = time.time()
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens,
            "extra_body": {
                "chat_template_kwargs": {"enable_thinking": False}
            },
        }
        if response_format:
            kwargs["response_format"] = response_format

        resp = self.client.chat.completions.create(**kwargs)
        elapsed = time.time() - start

        usage = resp.usage
        tokens = (usage.prompt_tokens + usage.completion_tokens) if usage else 0
        self.total_tokens += tokens
        self.call_count += 1

        result = {
            "content": resp.choices[0].message.content,
            "tokens": tokens,
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "latency_s": elapsed,
            "model": self.model,
        }

        # Auto-trace every LLM call
        tracer.trace_llm_call(
            messages=messages,
            response=result,
            step=self._current_step,
            prospect_id=self._current_prospect_id,
        )

        return result

    def set_context(self, step: str = "", prospect_id: str = ""):
        """Set context for the next LLM call (used by pipeline steps)."""
        self._current_step = step
        self._current_prospect_id = prospect_id

    def complete_json(self, messages: list[dict], **kwargs) -> dict:
        """Complete and parse response as JSON. Handles markdown-wrapped JSON."""
        result = self.complete(messages, **kwargs)
        raw = result["content"].strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            # Remove first line (```json or ```) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw = "\n".join(lines).strip()

        # Strip <think>...</think> blocks (Qwen reasoning)
        if "<think>" in raw:
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

        try:
            result["parsed"] = json.loads(raw)
        except json.JSONDecodeError:
            # Last resort: find first { and last }
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1:
                result["parsed"] = json.loads(raw[start:end + 1])
            else:
                raise ValueError(f"Could not parse JSON from LLM response: {raw[:200]}")

        return result

    @property
    def stats(self) -> dict:
        return {
            "mode": self.mode,
            "model": self.model,
            "calls": self.call_count,
            "total_tokens": self.total_tokens,
        }


# Module-level singletons
_dev_client: Optional[LLMClient] = None
_eval_client: Optional[LLMClient] = None


def get_llm(mode: str = "dev") -> LLMClient:
    global _dev_client, _eval_client
    if mode == "dev":
        if _dev_client is None:
            _dev_client = LLMClient("dev")
        return _dev_client
    if _eval_client is None:
        _eval_client = LLMClient("eval")
    return _eval_client
