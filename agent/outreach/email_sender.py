"""Email sender — routes through Resend or local sink based on kill switch."""

from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import settings
from agent.observability.tracer import tracer

logger = logging.getLogger(__name__)


class EmailSender:
    def __init__(self):
        self._resend_client = None
        self._sink_dir = Path("data/outbound_sink/emails")
        self._sink_dir.mkdir(parents=True, exist_ok=True)

    def send(
        self,
        to_email: str,
        subject: str,
        body: str,
        prospect_id: str = "",
        metadata: Optional[dict] = None,
    ) -> dict:
        """Send email via Resend (live) or local sink (default)."""
        record = {
            "to": to_email,
            "from": settings.from_email,
            "subject": subject,
            "body": body,
            "prospect_id": prospect_id,
            "metadata": metadata or {},
            "draft": True,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if settings.is_live and settings.resend_api_key:
            result = self._send_resend(record)
        else:
            result = self._send_to_sink(record)

        tracer.trace_outbound(
            action="email_send",
            prospect_id=prospect_id,
            channel="email",
            content_preview=f"To: {to_email} | Subject: {subject}",
            metadata={"status": result["status"]},
        )
        return result

    def _send_resend(self, record: dict) -> dict:
        try:
            import resend
            resend.api_key = settings.resend_api_key
            resp = resend.Emails.send({
                "from": record["from"],
                "to": [record["to"]],
                "subject": record["subject"],
                "text": record["body"],
                "headers": {"X-Draft": "true", "X-Prospect-ID": record.get("prospect_id", "")},
            })
            record["status"] = "sent"
            record["resend_id"] = resp.get("id", "")
            logger.info(f"Email sent via Resend to {record['to']}: {resp.get('id')}")
        except Exception as e:
            record["status"] = "failed"
            record["error"] = str(e)
            logger.error(f"Resend send failed: {e}")
        self._log_to_sink(record)
        return record

    def _send_to_sink(self, record: dict) -> dict:
        record["status"] = "sink"
        self._log_to_sink(record)
        logger.info(f"Email routed to local sink: {record['to']} — {record['subject']}")
        return record

    def _log_to_sink(self, record: dict):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        pid = record.get("prospect_id", "unknown")
        filename = f"{ts}_{pid}.json"
        (self._sink_dir / filename).write_text(json.dumps(record, indent=2, default=str))
