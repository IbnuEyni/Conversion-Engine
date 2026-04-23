"""Conversation manager — multi-turn thread handling with reply classification."""

from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path

from agent.models import Prospect, ConversationState, ReplyClass
from agent.llm_client import get_llm
from config.settings import settings

logger = logging.getLogger(__name__)

CLASSIFY_REPLY_PROMPT = """Classify this prospect reply into exactly one class.

Classes:
- engaged: Substantive response with specific question or context
- curious: "Tell me more" or "What do you do exactly?"
- hard_no: "Not interested" / "Please remove" / "Stop emailing"
- soft_defer: "Not right now" / "Ask in Q3" / "Too busy"
- objection: Specific objection (price, offshore, incumbent vendor)
- ambiguous: Cannot determine — route to human

Prospect reply: "{message}"

Output JSON: {{"reply_class": "engaged|curious|hard_no|soft_defer|objection|ambiguous", "objection_type": "pricing|incumbent_vendor|small_poc|none"}}"""

REPLY_PROMPT = """You are a sales development agent for Tenacious Consulting & Outsourcing.

## Style Rules (from style_guide.md)
- Direct, not aggressive. Grounded, not generic. Peer-to-peer.
- Honest about uncertainty. If you don't know, say so.
- Non-condescending. Frame gaps as research findings, not failures.
- Professional. Language for founders, CTOs, VPs of Engineering.
- Never use: "leverage our expertise", "best-in-class", "synergy", "touch base", "circle back"
- Never commit capacity not in bench summary.
- Max 150 words for engaged replies, 90 for curious, 60 for soft defer.
- One clear ask per message.

## Reply Class: {reply_class}
## Objection Type: {objection_type}

## Objection Handling Patterns (from discovery transcripts)
- Pricing: "We're not the cheapest. We compete on reliability and retention, not hourly rate. Average tenure 18 months, 3-hour minimum overlap."
- Incumbent vendor: "We don't aim to replace your current partner, but to fill a specific gap."
- Small POC: "We excel at starting small. Fixed-scope starter projects from $[PROJECT_ACV_MIN] to prove value quickly."

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
- If reply_class is "engaged": Reply with grounded answer, propose discovery call
- If reply_class is "curious": Reply with targeted 3-sentence context + Cal link
- If reply_class is "hard_no": Do NOT reply. Mark opted out.
- If reply_class is "soft_defer": Close gracefully with specific re-engagement month
- If reply_class is "objection": Use objection handling pattern above
- If reply_class is "ambiguous": Route to human

## Human Handoff Rules (mandatory)
Hand off to human when:
1. Prospect asks for pricing outside public bands
2. Prospect asks for specific staffing beyond bench_summary
3. Prospect asks for public client reference
4. Prospect references regulatory/legal terms
5. Prospect is C-level at company above 2,000 headcount

## Output (JSON)
{{
  "reply_text": "your reply (empty string if hard_no)",
  "next_state": "engaged" | "qualified" | "call_booked" | "stalled" | "opted_out",
  "should_book_call": true/false,
  "should_switch_to_sms": false,
  "needs_human_handoff": true/false,
  "handoff_reason": "reason if needs_human_handoff is true"
}}"""


class ConversationManager:
    def __init__(self):
        self._threads: dict[str, list[dict]] = {}
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

        # Step 1: Classify the reply
        reply_class, objection_type = self._classify_reply(message)

        # Step 2: Handle hard_no immediately
        if reply_class == ReplyClass.HARD_NO:
            return {
                "reply_text": "",
                "next_state": "opted_out",
                "should_book_call": False,
                "should_switch_to_sms": False,
                "needs_human_handoff": False,
                "handoff_reason": "",
            }

        # Step 3: Handle ambiguous — route to human
        if reply_class == ReplyClass.AMBIGUOUS:
            return {
                "reply_text": "",
                "next_state": "engaged",
                "should_book_call": False,
                "should_switch_to_sms": False,
                "needs_human_handoff": True,
                "handoff_reason": "Ambiguous reply — cannot classify with confidence",
            }

        # Step 4: Generate reply
        history = self._threads.get(prospect.id, [])
        history_text = "\n".join(
            f"[{m['role']}] ({m['channel']}, {m['timestamp'][:16]}): {m['content'][:500]}"
            for m in history[-10:]
        )

        brief = prospect.signal_brief
        signal_summary = "No signal data"
        if brief:
            parts = []
            if brief.buying_window_signals.funding_event.detected:
                parts.append(f"Funding: {brief.buying_window_signals.funding_event.stage}")
            parts.append(f"AI Maturity: {brief.ai_maturity.score}/3")
            if brief.hiring_velocity.open_roles_today > 0:
                parts.append(f"Open roles: {brief.hiring_velocity.open_roles_today}")
            signal_summary = "; ".join(parts)

        bench_info = self._load_bench_summary()

        prompt = REPLY_PROMPT.format(
            reply_class=reply_class.value,
            objection_type=objection_type,
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
            {"role": "system", "content": "You are a professional B2B sales agent for Tenacious. Output valid JSON only."},
            {"role": "user", "content": prompt},
        ], max_tokens=1024)

        parsed = result["parsed"]
        if parsed.get("reply_text"):
            self.add_message(prospect.id, "agent", parsed["reply_text"], prospect.channel.value)

        return {
            "reply_text": parsed.get("reply_text", ""),
            "next_state": parsed.get("next_state", "engaged"),
            "should_book_call": parsed.get("should_book_call", False),
            "should_switch_to_sms": parsed.get("should_switch_to_sms", False),
            "needs_human_handoff": parsed.get("needs_human_handoff", False),
            "handoff_reason": parsed.get("handoff_reason", ""),
            "reply_class": reply_class.value,
            "tokens_used": result["tokens"],
            "latency_s": result["latency_s"],
        }

    def _classify_reply(self, message: str) -> tuple[ReplyClass, str]:
        """Classify inbound reply into one of 5 classes."""
        llm = get_llm("dev")
        result = llm.complete_json([
            {"role": "system", "content": "Classify the reply. Output valid JSON only."},
            {"role": "user", "content": CLASSIFY_REPLY_PROMPT.format(message=message)},
        ], max_tokens=128)
        parsed = result["parsed"]
        try:
            reply_class = ReplyClass(parsed.get("reply_class", "ambiguous"))
        except ValueError:
            reply_class = ReplyClass.AMBIGUOUS
        return reply_class, parsed.get("objection_type", "none")

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
        lines = [f"Total: {bench.get('total_engineers_on_bench', 0)} engineers"]
        for stack, info in bench.get("stacks", {}).items():
            lines.append(f"  {stack}: {info['available_engineers']}")
        return "\n".join(lines)
