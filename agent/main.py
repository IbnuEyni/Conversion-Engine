"""Conversion Engine — FastAPI orchestrator."""

from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from agent.models import Prospect, ConversationState, Channel
from agent.enrichment.pipeline import EnrichmentPipeline
from agent.qualification.classifier import classify_prospect
from agent.outreach.email_composer import EmailComposer
from agent.outreach.email_sender import EmailSender
from agent.outreach.sms_handler import SMSHandler
from agent.conversation.manager import ConversationManager
from agent.booking.engine import BookingEngine
from agent.crm.hubspot import HubSpotCRM
from config.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Conversion Engine", version="0.1.0")

# Components
enrichment = EnrichmentPipeline()
composer = EmailComposer()
sender = EmailSender()
sms = SMSHandler()
conversations = ConversationManager()
booking = BookingEngine()
crm = HubSpotCRM()

# In-memory prospect store (swap for DB in production)
prospects: dict[str, Prospect] = {}


# --- Request Models ---

class ProspectInput(BaseModel):
    company_name: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    contact_title: str | None = None


class ReplyInput(BaseModel):
    prospect_id: str
    message: str
    channel: str = "email"


# --- Endpoints ---

@app.get("/health")
def health():
    return {
        "status": "ok",
        "live_mode": settings.is_live,
        "kill_switch": "ENGAGED" if not settings.live_mode else "DISENGAGED",
        "hubspot": "connected" if crm.is_connected else "sink_mode",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/hubspot/setup")
def setup_hubspot_properties():
    """Create custom HubSpot properties. Run once during initial setup."""
    crm.ensure_custom_properties()
    return {"status": "properties created", "connected": crm.is_connected}


@app.post("/prospects/{prospect_id}/sync")
def sync_to_hubspot(prospect_id: str):
    """Force sync a prospect to HubSpot."""
    prospect = prospects.get(prospect_id)
    if not prospect:
        raise HTTPException(404, "Prospect not found")
    return crm.sync_prospect(prospect)


@app.post("/prospects/enrich")
def enrich_prospect(inp: ProspectInput):
    """Enrich a prospect with all available signals."""
    pid = str(uuid.uuid4())[:8]
    prospect = Prospect(
        id=pid,
        company_name=inp.company_name,
        contact_name=inp.contact_name,
        contact_email=inp.contact_email,
        contact_phone=inp.contact_phone,
        contact_title=inp.contact_title,
    )

    prospect = enrichment.enrich(prospect)
    prospect.classification = classify_prospect(prospect)
    prospects[pid] = prospect
    enrichment.save_brief(prospect)

    # Sync to HubSpot
    hubspot_result = crm.sync_prospect(prospect)

    return {
        "prospect_id": pid,
        "company": prospect.company_name,
        "segment": prospect.classification.segment.value,
        "confidence": prospect.classification.confidence,
        "ai_maturity": prospect.signal_brief.ai_maturity.score if prospect.signal_brief else None,
        "bench_match": prospect.classification.bench_match,
        "state": prospect.state.value,
        "hubspot": hubspot_result,
    }


@app.post("/prospects/{prospect_id}/outreach")
def send_outreach(prospect_id: str):
    """Compose and send outreach email for an enriched prospect."""
    prospect = prospects.get(prospect_id)
    if not prospect:
        raise HTTPException(404, "Prospect not found")
    if prospect.state not in (ConversationState.ENRICHED, ConversationState.NEW):
        raise HTTPException(400, f"Prospect in state {prospect.state.value}, cannot send outreach")

    email = composer.compose(prospect)
    result = sender.send(
        to_email=prospect.contact_email or f"synthetic+{prospect_id}@sink.local",
        subject=email["subject"],
        body=email["body"],
        prospect_id=prospect_id,
        metadata={"signal_references": email.get("signal_references", [])},
    )

    prospect.state = ConversationState.OUTREACH_SENT
    prospect.emails_sent += 1
    prospect.last_contact = datetime.utcnow()
    conversations.add_message(prospect_id, "agent", email["body"], "email")

    # Log outreach to HubSpot
    crm.log_event(prospect, "outreach_email", f"Subject: {email['subject']}\n\n{email['body']}")
    crm.upsert_contact(prospect)  # update state + emails_sent

    return {
        "prospect_id": prospect_id,
        "email_subject": email["subject"],
        "status": result["status"],
        "confidence_level": email.get("confidence_level"),
        "signal_references": email.get("signal_references", []),
        "tokens_used": email.get("tokens_used"),
    }


@app.post("/prospects/{prospect_id}/reply")
def handle_reply(prospect_id: str, inp: ReplyInput):
    """Handle an inbound reply from a prospect."""
    prospect = prospects.get(prospect_id)
    if not prospect:
        raise HTTPException(404, "Prospect not found")

    result = conversations.handle_reply(prospect, inp.message)

    # Update state
    state_map = {
        "engaged": ConversationState.ENGAGED,
        "qualified": ConversationState.QUALIFIED,
        "call_booked": ConversationState.CALL_BOOKED,
        "stalled": ConversationState.STALLED,
        "opted_out": ConversationState.OPTED_OUT,
    }
    new_state = state_map.get(result["next_state"], ConversationState.ENGAGED)
    prospect.state = new_state
    prospect.updated_at = datetime.utcnow()

    # Log to HubSpot
    crm.log_event(prospect, "reply_handled", f"Prospect said: {inp.message}\n\nAgent replied: {result['reply_text']}")
    crm.upsert_contact(prospect)
    if new_state == ConversationState.QUALIFIED:
        crm.create_deal(prospect)

    # Send reply
    if prospect.channel == Channel.EMAIL:
        sender.send(
            to_email=prospect.contact_email or f"synthetic+{prospect_id}@sink.local",
            subject=f"Re: {prospect.company_name}",
            body=result["reply_text"],
            prospect_id=prospect_id,
        )
    elif prospect.channel == Channel.SMS:
        sms.send(
            to_phone=prospect.contact_phone or "+1234567890",
            message=result["reply_text"][:160],
            prospect_id=prospect_id,
        )

    return {
        "prospect_id": prospect_id,
        "reply": result["reply_text"],
        "state": new_state.value,
        "should_book_call": result["should_book_call"],
        "needs_human_handoff": result["needs_human_handoff"],
    }


@app.post("/webhooks/email/reply")
async def email_reply_webhook(request: Request):
    """Webhook for inbound email replies (Resend)."""
    body = await request.json()
    logger.info(f"Email webhook received: {json.dumps(body)[:200]}")
    return {"status": "received"}


@app.post("/webhooks/sms/inbound")
async def sms_inbound_webhook(request: Request):
    """Webhook for inbound SMS (Africa's Talking)."""
    body = await request.json()
    from_phone = body.get("from", "")
    message = body.get("text", "")
    result = sms.handle_inbound(from_phone, message)
    logger.info(f"SMS webhook: {from_phone} -> {result['action']}")
    return result


@app.get("/prospects")
def list_prospects():
    """List all prospects and their states."""
    return [
        {
            "id": p.id,
            "company": p.company_name,
            "segment": p.classification.segment.value if p.classification else "none",
            "state": p.state.value,
            "emails_sent": p.emails_sent,
        }
        for p in prospects.values()
    ]


@app.get("/prospects/{prospect_id}")
def get_prospect(prospect_id: str):
    prospect = prospects.get(prospect_id)
    if not prospect:
        raise HTTPException(404, "Prospect not found")
    return prospect.model_dump(mode="json")


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
