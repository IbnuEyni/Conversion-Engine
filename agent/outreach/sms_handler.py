"""SMS handler — Africa's Talking sandbox for warm-lead scheduling."""

from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path

from config.settings import settings

logger = logging.getLogger(__name__)


class SMSHandler:
    def __init__(self):
        self._at_client = None
        self._sink_dir = Path("data/outbound_sink/sms")
        self._sink_dir.mkdir(parents=True, exist_ok=True)

    def _get_client(self):
        if self._at_client is None and settings.at_api_key:
            import africastalking
            africastalking.initialize(settings.at_username, settings.at_api_key)
            self._at_client = africastalking.SMS
        return self._at_client

    def send(self, to_phone: str, message: str, prospect_id: str = "") -> dict:
        record = {
            "to": to_phone,
            "message": message,
            "prospect_id": prospect_id,
            "timestamp": datetime.utcnow().isoformat(),
            "draft": True,
        }

        if settings.is_live and settings.at_api_key:
            return self._send_at(record)
        return self._send_to_sink(record)

    def _send_at(self, record: dict) -> dict:
        try:
            client = self._get_client()
            resp = client.send(record["message"], [record["to"]], settings.at_shortcode)
            record["status"] = "sent"
            record["at_response"] = str(resp)
            logger.info(f"SMS sent via AT to {record['to']}")
        except Exception as e:
            record["status"] = "failed"
            record["error"] = str(e)
            logger.error(f"AT SMS failed: {e}")
        self._log(record)
        return record

    def _send_to_sink(self, record: dict) -> dict:
        record["status"] = "sink"
        self._log(record)
        logger.info(f"SMS routed to sink: {record['to']}")
        return record

    def _log(self, record: dict):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        pid = record.get("prospect_id", "unknown")
        (self._sink_dir / f"{ts}_{pid}.json").write_text(
            json.dumps(record, indent=2, default=str)
        )

    def handle_inbound(self, from_phone: str, message: str) -> dict:
        """Handle inbound SMS — check for STOP/HELP, route to conversation."""
        msg_upper = message.strip().upper()

        if msg_upper in ("STOP", "UNSUBSCRIBE", "UNSUB", "QUIT", "END"):
            logger.info(f"STOP received from {from_phone}")
            return {"action": "opt_out", "from": from_phone}

        if msg_upper in ("HELP", "INFO"):
            self.send(
                from_phone,
                "Tenacious Consulting & Outsourcing. Reply STOP to opt out. "
                "For questions: hello@tenacious.dev",
            )
            return {"action": "help_sent", "from": from_phone}

        return {"action": "route_to_conversation", "from": from_phone, "message": message}
