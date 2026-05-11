"""Conversion Engine — FastAPI orchestrator."""

from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

    # Backfill segment into the signal brief per schema requirement
    if prospect.signal_brief and prospect.classification:
        prospect.signal_brief.primary_segment_match = prospect.classification.segment.value
        prospect.signal_brief.segment_confidence = prospect.classification.confidence

    prospects[pid] = prospect
    enrichment.save_brief(prospect)

    # Sync to HubSpot
    try:
        hubspot_result = crm.sync_prospect(prospect)
    except Exception as e:
        hubspot_result = {"status": "error", "error": str(e)}

    return {
        "prospect_id": pid,
        "company": prospect.company_name,
        "segment": prospect.classification.segment.value,
        "confidence": prospect.classification.confidence,
        "ai_maturity": prospect.signal_brief.ai_maturity.score if prospect.signal_brief else None,
        "bench_match": prospect.classification.bench_match,
        "state": prospect.state.value,
        "honesty_flags": prospect.signal_brief.honesty_flags if prospect.signal_brief else [],
        "hiring_velocity": prospect.signal_brief.hiring_velocity.velocity_label.value if prospect.signal_brief else None,
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

    try:
        email = composer.compose(prospect)
    except Exception as e:
        logger.error(f"Email compose failed for {prospect_id}: {e}")
        raise HTTPException(500, f"Email composition failed: {e}")

    result = sender.send(
        to_email=prospect.contact_email or f"synthetic-{prospect_id}@example.com",
        subject=email["subject"],
        body=email["body"],
        prospect_id=prospect_id,
        metadata={"signal_references": email.get("signal_references", [])},
    )

    prospect.state = ConversationState.OUTREACH_SENT
    prospect.emails_sent += 1
    prospect.last_contact = datetime.utcnow()
    conversations.add_message(prospect_id, "agent", email["body"], "email")

    try:
        crm.log_event(prospect, "outreach_email", f"Subject: {email['subject']}\n\n{email['body']}")
        crm.upsert_contact(prospect)
    except Exception as e:
        logger.warning(f"HubSpot log failed: {e}")

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

    try:
        result = conversations.handle_reply(prospect, inp.message)
    except Exception as e:
        logger.error(f"Reply handling failed for {prospect_id}: {e}")
        raise HTTPException(500, f"Reply handling failed: {e}")

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

    try:
        crm.log_event(prospect, "reply_handled", f"Prospect said: {inp.message}\n\nAgent replied: {result['reply_text']}")
        crm.upsert_contact(prospect)
        if new_state == ConversationState.QUALIFIED:
            crm.create_deal(prospect)
    except Exception as e:
        logger.warning(f"HubSpot log failed: {e}")

    booking_link = ""
    booking_confirmation = None

    if result.get("reply_text"):
        if result.get("should_book_call"):
            booking_link = booking.generate_booking_link(
                prospect_name=prospect.contact_name or prospect.company_name,
                prospect_email=prospect.contact_email or f"synthetic-{prospect_id}@example.com",
                prospect_id=prospect_id,
            )
            booking_confirmation = booking.book_slot_sync(
                prospect_name=prospect.contact_name or prospect.company_name,
                prospect_email=prospect.contact_email or f"synthetic-{prospect_id}@example.com",
                notes=f"Discovery call for {prospect.company_name}",
                prospect_id=prospect_id,
            )
            prospect.calcom_booking_id = booking_confirmation.get("calcom_booking_id", "")
            prospect.state = ConversationState.CALL_BOOKED
            new_state = ConversationState.CALL_BOOKED

        reply_body = result["reply_text"]
        if booking_link:
            reply_body += f"\n\nBook your discovery call here: {booking_link}"

        if prospect.channel == Channel.EMAIL:
            sender.send(
                to_email=prospect.contact_email or f"synthetic-{prospect_id}@example.com",
                subject=f"Re: {prospect.company_name}",
                body=reply_body,
                prospect_id=prospect_id,
            )
            prospect.emails_sent += 1
            prospect.last_contact = datetime.utcnow()
        elif prospect.channel == Channel.SMS:
            is_warm = prospect.state in (
                ConversationState.ENGAGED, ConversationState.QUALIFIED,
                ConversationState.CALL_BOOKED, ConversationState.HANDED_OFF,
            )
            sms_body = result["reply_text"][:120]
            if booking_link:
                sms_body = f"{result['reply_text'][:80]}\nBook: {booking_link}"
            sms.send(
                to_phone=prospect.contact_phone or "+1234567890",
                message=sms_body[:160],
                prospect_id=prospect_id,
                is_warm_lead=is_warm,
            )

    return {
        "prospect_id": prospect_id,
        "reply": result["reply_text"],
        "state": new_state.value,
        "reply_class": result.get("reply_class", "unknown"),
        "should_book_call": result["should_book_call"],
        "needs_human_handoff": result["needs_human_handoff"],
        "booking": booking_confirmation,
    }


@app.post("/webhooks/email/reply")
async def email_reply_webhook(request: Request):
    """Webhook for inbound email replies (Resend)."""
    body = await request.json()
    logger.info(f"Email webhook received: {json.dumps(body)[:200]}")

    event_type = body.get("type", "")

    # Handle delivery failure events
    if event_type in ("email.bounced", "email.complained"):
        email_to = body.get("data", {}).get("to", [""])
        if isinstance(email_to, list):
            email_to = email_to[0] if email_to else ""
        logger.warning(f"Email delivery failure ({event_type}): {email_to}")
        # Find prospect by email and mark as failed
        for p in prospects.values():
            if p.contact_email == email_to:
                p.state = ConversationState.STALLED
                try:
                    crm.upsert_contact(p)
                except Exception:
                    pass
                break
        return {"status": "failure_logged", "event": event_type}

    # Handle inbound reply
    reply_text = body.get("data", {}).get("text", "") or body.get("text", "") or body.get("message", "")
    from_email = body.get("data", {}).get("from", "") or body.get("from", "")

    if reply_text and from_email:
        # Find prospect by email
        matched_prospect = None
        for p in prospects.values():
            if p.contact_email and p.contact_email.lower() == from_email.lower():
                matched_prospect = p
                break

        if matched_prospect:
            try:
                result = conversations.handle_reply(matched_prospect, reply_text)
                state_map = {
                    "engaged": ConversationState.ENGAGED,
                    "qualified": ConversationState.QUALIFIED,
                    "call_booked": ConversationState.CALL_BOOKED,
                    "stalled": ConversationState.STALLED,
                    "opted_out": ConversationState.OPTED_OUT,
                }
                matched_prospect.state = state_map.get(result["next_state"], ConversationState.ENGAGED)
                matched_prospect.updated_at = datetime.utcnow()

                # Send agent reply
                if result.get("reply_text"):
                    sender.send(
                        to_email=matched_prospect.contact_email,
                        subject=f"Re: {matched_prospect.company_name}",
                        body=result["reply_text"],
                        prospect_id=matched_prospect.id,
                    )

                try:
                    crm.log_event(matched_prospect, "webhook_reply", f"Prospect: {reply_text}\nAgent: {result['reply_text']}")
                    crm.upsert_contact(matched_prospect)
                except Exception:
                    pass

                logger.info(f"Webhook reply processed for {matched_prospect.company_name}: state={matched_prospect.state.value}")
                return {"status": "reply_processed", "prospect_id": matched_prospect.id, "state": matched_prospect.state.value}
            except Exception as e:
                logger.error(f"Webhook reply handling failed: {e}")
                return {"status": "error", "detail": str(e)}

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


@app.post("/webhooks/calcom/booking")
async def calcom_booking_webhook(request: Request):
    """Webhook for Cal.com booking confirmations."""
    body = await request.json()
    logger.info(f"Cal.com webhook received: {json.dumps(body)[:200]}")
    result = booking.confirm_booking(body)

    # Find and update prospect by email
    attendee_email = result.get("prospect_email", "")
    for p in prospects.values():
        if p.contact_email and p.contact_email.lower() == attendee_email.lower():
            p.state = ConversationState.CALL_BOOKED
            p.calcom_booking_id = result.get("calcom_booking_id", "")
            p.updated_at = datetime.utcnow()
            try:
                crm.upsert_contact(p)
                crm.log_event(p, "calcom_booking_confirmed", f"Booking ID: {result.get('calcom_booking_id')}")
            except Exception:
                pass
            break

    return {"status": "booking_confirmed", **result}


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


@app.get("/prospects/{prospect_id}/thread")
def get_thread(prospect_id: str):
    """Get conversation thread for a prospect."""
    if prospect_id not in prospects:
        raise HTTPException(404, "Prospect not found")
    return conversations.get_thread(prospect_id)


@app.get("/stats/pipeline")
def pipeline_stats():
    """Get pipeline state counts for dashboard."""
    counts: dict[str, int] = {}
    for p in prospects.values():
        state = p.state.value
        counts[state] = counts.get(state, 0) + 1
    return counts


@app.get("/stats/analytics")
def analytics_stats():
    """Get analytics data for charts."""
    segment_counts: dict[str, int] = {}
    state_counts: dict[str, int] = {}
    reply_classes: dict[str, int] = {}
    total_emails = 0
    total_replies = 0
    total_booked = 0
    total_opted_out = 0

    for p in prospects.values():
        seg = p.classification.segment.value if p.classification else "unclassified"
        segment_counts[seg] = segment_counts.get(seg, 0) + 1
        state = p.state.value
        state_counts[state] = state_counts.get(state, 0) + 1
        total_emails += p.emails_sent
        if state in ("engaged", "qualified", "call_booked", "handed_off"):
            total_replies += 1
        if state == "call_booked":
            total_booked += 1
        if state == "opted_out":
            total_opted_out += 1

    # Get reply class distribution from conversation threads
    for pid in prospects:
        thread = conversations.get_thread(pid)
        for msg in thread:
            if msg.get("role") == "prospect":
                total_replies += 0  # already counted above

    # Funnel data
    total_prospects = len(prospects)
    enriched = sum(1 for p in prospects.values() if p.state.value != "new")
    outreach_sent = sum(1 for p in prospects.values() if p.emails_sent > 0)
    engaged = sum(1 for p in prospects.values() if p.state.value in ("engaged", "qualified", "call_booked", "handed_off"))
    qualified = sum(1 for p in prospects.values() if p.state.value in ("qualified", "call_booked", "handed_off"))
    booked = sum(1 for p in prospects.values() if p.state.value == "call_booked")

    return {
        "segment_counts": segment_counts,
        "state_counts": state_counts,
        "funnel": [
            {"stage": "Prospects", "count": total_prospects},
            {"stage": "Enriched", "count": enriched},
            {"stage": "Outreach Sent", "count": outreach_sent},
            {"stage": "Engaged", "count": engaged},
            {"stage": "Qualified", "count": qualified},
            {"stage": "Call Booked", "count": booked},
        ],
        "totals": {
            "prospects": total_prospects,
            "emails_sent": total_emails,
            "replies": total_replies,
            "calls_booked": total_booked,
            "opted_out": total_opted_out,
            "reply_rate": round(total_replies / max(outreach_sent, 1) * 100, 1),
            "booking_rate": round(total_booked / max(total_replies, 1) * 100, 1),
        },
    }


@app.get("/threads")
def list_threads():
    """List all active conversation threads."""
    threads = []
    for pid, prospect in prospects.items():
        thread = conversations.get_thread(pid)
        if thread:
            last_msg = thread[-1] if thread else None
            threads.append({
                "prospect_id": pid,
                "company": prospect.company_name,
                "contact_name": prospect.contact_name,
                "state": prospect.state.value,
                "message_count": len(thread),
                "last_message": last_msg,
                "segment": prospect.classification.segment.value if prospect.classification else "none",
            })
    return sorted(threads, key=lambda t: t["last_message"]["timestamp"] if t["last_message"] else "", reverse=True)


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
