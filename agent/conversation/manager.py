"""Conversation manager — multi-turn thread handling with state machine."""

from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from agent.models import Prospect, ConversationState, Channel
from agent.llm_client import get_llm
from config.settings import settings

logger = logging.getLogger(__name__)

REPLY_PROMPT = """You are a sales development agent for Tenacious Consulting & Outsourcing.
You are in an ongoing email conversation with a prospect.

## Style Rules
- Direct, not aggressive. Grounded, not generic. Peer-to-peer.
- If you don't know something, say so. Never fabricate.
- Never commit to capacity not in the bench summary.
- If the prospect asks for specific pricing beyond public bands, say you'll connect them with a delivery lead.
- If the prospect wants to schedule a call, offer specific times from the calendar.
- Keep responses concise — 2-3 paragraphs max.

## Prospect Context
Company: {company_name}
Contact: {contact_name} ({contact_title})
Segment: {segment}
Signal Brief Summary: {signal_summary}
Bench Availability: {bench_info}

## Conversation History
{conversation_history}

## Latest Message from Prospect
{latest_message}

## Instructions
Respond appropriately. Determine the next action:
- If prospect is interested → qualify further or offer to book a call
- If prospect asks about pricing → share public bands, offer call for details
- If prospect asks about specific capacity → check bench, be honest
- If prospect wants to schedule → propose times
- If prospect is not interested → thank them, close gracefully
- If prospect is hostile/rude → stay professional, offer to stop

## Output (JSON)
{{
  "reply_text": "your reply to the prospect",
  "next_state": "engaged" | "qualified" | "call_booked" | "stalled" | "opted_out",
  "should_book_call": true/false,
  "should_switch_to_sms": true/false,
  "needs_human_handoff": true/false,
  "handoff_reason": "reason if needs_human_handoff is true"
}}"""


class ConversationManager:
    def __init__(self):
        self._threads: dict[str, list[dict]] = {}  # prospect_id -> messages
        self._store_dir = Path("data/conversations")
        self._store_dir.mkdir(parents=True, exist_ok=True)

    def add_message(self, prospect_id: str, role: str, content: str, channel: str = "email"):
        if prospect_id not in self._threads:
            self._threads[prospect_id] = []
        self._threads[prospect_id].append({
            "role": role,
            "content": content,
            "channel": channel,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self._persist(prospect_id)

    def handle_reply(self, prospect: Prospect, message: str) -> dict:
        """Handle an inbound reply from a prospect."""
        self.add_message(prospect.id, "prospect", message, prospect.channel.value)

        history = self._threads.get(prospect.id, [])
        history_text = "\n".join(
            f"[{m['role']}] ({m['channel']}, {m['timestamp'][:16]}): {m['content'][:500]}"
            for m in history[-10:]  # last 10 messages
        )

        brief = prospect.signal_brief
        signal_summary = "No signal data"
        if brief:
            parts = []
            if brief.funding.strength.value != "absent":
                parts.append(f"Funding: {brief.funding.round_type}")
            parts.append(f"AI Maturity: {brief.ai_maturity.score}/3")
            signal_summary = "; ".join(parts)

        bench_info = self._load_bench_summary()

        prompt = REPLY_PROMPT.format(
            company_name=prospect.company_name,
            contact_name=prospect.contact_name or "there",
            contact_title=prospect.contact_title or "Engineering Leader",
            segment=prospect.classification.segment.value if prospect.classification else "unclassified",
            signal_summary=signal_summary,
            bench_info=bench_info,
            conversation_history=history_text,
            latest_message=message,
        )

        llm = get_llm("dev")
        result = llm.complete_json([
            {"role": "system", "content": "You are a professional B2B sales agent. Output valid JSON only."},
            {"role": "user", "content": prompt},
        ], max_tokens=1024)

        parsed = result["parsed"]
        self.add_message(prospect.id, "agent", parsed["reply_text"], prospect.channel.value)

        return {
            "reply_text": parsed["reply_text"],
            "next_state": parsed.get("next_state", "engaged"),
            "should_book_call": parsed.get("should_book_call", False),
            "should_switch_to_sms": parsed.get("should_switch_to_sms", False),
            "needs_human_handoff": parsed.get("needs_human_handoff", False),
            "handoff_reason": parsed.get("handoff_reason", ""),
            "tokens_used": result["tokens"],
            "latency_s": result["latency_s"],
        }

    def get_thread(self, prospect_id: str) -> list[dict]:
        return self._threads.get(prospect_id, [])

    def _persist(self, prospect_id: str):
        path = self._store_dir / f"{prospect_id}.json"
        path.write_text(json.dumps(self._threads[prospect_id], indent=2, default=str))

    def _load_bench_summary(self) -> str:
        p = Path(settings.seed_data_path) / "bench_summary.json"
        if not p.exists():
            return "Bench data not available"
        bench = json.loads(p.read_text())
        lines = [f"Total: {bench.get('total_available', 0)} engineers"]
        for stack, info in bench.get("by_stack", {}).items():
            lines.append(f"  {stack}: {info['available']}")
        return "\n".join(lines)
