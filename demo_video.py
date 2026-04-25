#!/usr/bin/env python3
"""
Demo Video Script — The Conversion Engine
Records the full end-to-end flow for the 8-minute submission video.

Run locally (recommended — no Render cold start):
  1. python3 -m agent.main &
  2. sleep 5
  3. python3 demo_video.py

Or against Render:
  python3 demo_video.py --render
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timedelta

import httpx

BASE_URL = "http://localhost:8000"
if "--render" in sys.argv:
    BASE_URL = "https://conversion-engine-2nti.onrender.com"

PAUSE = 2


def banner(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def narrate(text):
    print(f"  🎙️  {text}")
    time.sleep(PAUSE)


async def main():
    client = httpx.AsyncClient(timeout=300.0)
    prospect_id = None

    # ── STEP 1: Health ──────────────────────────────────────
    banner("STEP 1: SYSTEM HEALTH CHECK")
    narrate("Verifying system status, kill switch, and HubSpot connection...")

    resp = await client.get(f"{BASE_URL}/health")
    health = resp.json()
    print(json.dumps(health, indent=2))
    print(f"\n  ✅ System is {'LIVE' if health['live_mode'] else 'in SAFE mode'}")
    print(f"  🏢 HubSpot: {health['hubspot']}")
    time.sleep(PAUSE)

    # ── STEP 2: Enrich ──────────────────────────────────────
    banner("STEP 2: ENRICH PROSPECT — Full Signal Collection")
    narrate("Running enrichment: Crunchbase, job posts, layoffs.fyi, leadership, AI maturity, gap analysis...")

    prospect_data = {
        "company_name": "Consolety",
        "contact_name": "Amara Osei",
        "contact_email": "delivered@resend.dev",
        "contact_phone": "+254700000001",
        "contact_title": "VP Engineering"
    }

    print(f"  📋 Company: {prospect_data['company_name']}")
    print(f"  👤 Contact: {prospect_data['contact_name']} ({prospect_data['contact_title']})")
    print()

    resp = await client.post(f"{BASE_URL}/prospects/enrich", json=prospect_data)
    enrichment = resp.json()
    prospect_id = enrichment["prospect_id"]

    print(f"  ✅ Prospect ID: {prospect_id}")
    print(f"  🎯 ICP Segment: {enrichment['segment']}")
    print(f"  📊 Confidence: {enrichment['confidence']}")
    print(f"  🤖 AI Maturity: {enrichment.get('ai_maturity', 'N/A')}/3")
    print(f"  📈 Hiring Velocity: {enrichment.get('hiring_velocity', 'N/A')}")
    print(f"  ⚠️  Honesty Flags: {enrichment.get('honesty_flags', [])}")

    hs = enrichment.get("hubspot", {})
    mode = hs.get("mode", "unknown") if isinstance(hs, dict) else str(hs)
    print(f"  🏢 HubSpot: {mode}")
    if isinstance(hs, dict) and hs.get("contact_id"):
        print(f"     Contact ID: {hs['contact_id']}")
        print(f"     Company ID: {hs.get('company_id', 'N/A')}")
    time.sleep(PAUSE)

    # ── STEP 3: Hiring Signal Brief ─────────────────────────
    banner("STEP 3: HIRING SIGNAL BRIEF — Per-Signal Confidence")
    narrate("Showing the full hiring signal brief with confidence scores per signal...")

    resp = await client.get(f"{BASE_URL}/prospects/{prospect_id}")
    full = resp.json()
    brief = full.get("signal_brief")

    if brief:
        bw = brief.get("buying_window_signals", {})
        funding = bw.get("funding_event", {})
        layoff = bw.get("layoff_event", {})
        hv = brief.get("hiring_velocity", {})
        lc = bw.get("leadership_change", {})
        ai = brief.get("ai_maturity", {})

        print(f"  💰 Funding:    detected={funding.get('detected')}  stage={funding.get('stage') or 'none'}")
        print(f"  📉 Layoffs:    detected={layoff.get('detected')}  headcount={layoff.get('headcount_reduction', 0)}  date={layoff.get('date', 'N/A')}")
        print(f"  📈 Hiring:     label={hv.get('velocity_label')}  roles={hv.get('open_roles_today', 0)}  confidence={hv.get('signal_confidence', 0)}")
        print(f"  👔 Leadership: detected={lc.get('detected')}  role={lc.get('role') or 'none'}")
        print(f"  🤖 AI Maturity: score={ai.get('score', 0)}/3  confidence={ai.get('confidence', 0)}")
        print(f"  🔧 Tech Stack: {brief.get('tech_stack', [])}")
        print(f"  ⚠️  Honesty Flags: {brief.get('honesty_flags', [])}")
        bench = brief.get("bench_to_brief_match", {})
        print(f"  🏋️  Bench: available={bench.get('bench_available')}  gaps={bench.get('gaps', [])}")
        print(f"  📅 Generated: {brief.get('generated_at')}")
    time.sleep(PAUSE)

    # ── STEP 4: Gap Brief ───────────────────────────────────
    banner("STEP 4: COMPETITOR GAP BRIEF")
    narrate("Showing competitor gap analysis with sector benchmarks...")

    gap = full.get("gap_brief")
    if gap:
        print(f"  🏭 Sector: {gap.get('prospect_sector', 'N/A')}")
        print(f"  📈 AI Maturity vs Top Quartile: {gap.get('prospect_ai_maturity_score')}/3 vs {gap.get('sector_top_quartile_benchmark')}")
        print(f"  🎯 Pitch Shift: {gap.get('suggested_pitch_shift', 'N/A')}")
        findings = gap.get("gap_findings", [])
        for i, f in enumerate(findings[:3], 1):
            print(f"  {i}. {f.get('practice', 'N/A')}")
    else:
        print("  ℹ️  No gap brief (no peers in Crunchbase sample for this sector)")
    time.sleep(PAUSE)

    # ── STEP 5: Outreach Email ──────────────────────────────
    banner("STEP 5: SIGNAL-GROUNDED OUTREACH EMAIL")
    narrate("Composing and sending email grounded in enrichment signals...")

    resp = await client.post(f"{BASE_URL}/prospects/{prospect_id}/outreach")
    outreach = resp.json()

    status = outreach.get("status", "unknown")
    print(f"  📬 Delivery: {status}")
    print(f"  📧 Subject: {outreach.get('email_subject', 'N/A')}")
    print(f"  🎯 Confidence: {outreach.get('confidence_level', 'N/A')}")
    print(f"  📊 Signals Used: {outreach.get('signal_references', [])}")
    print(f"  🔤 Tokens: {outreach.get('tokens_used', 'N/A')}")

    if status == "sent":
        print(f"\n  ✅ Email delivered via Resend!")
    elif status == "sink":
        print(f"\n  ℹ️  Email saved to local sink (LIVE_MODE=false)")
    elif status == "failed":
        print(f"\n  ⚠️  Resend delivery failed — email logged locally")
    time.sleep(PAUSE)

    # ── STEP 6: Prospect Reply ──────────────────────────────
    banner("STEP 6: PROSPECT REPLIES — Qualification")
    narrate("Prospect replies with interest in ML engineers — triggers qualification...")

    reply_data = {
        "prospect_id": prospect_id,
        "message": (
            "Hi! This is interesting — we've been looking at scaling our "
            "engineering team, especially on the AI/ML side. We recently lost "
            "a few senior engineers and need to rebuild. Can you tell me more "
            "about your ML bench availability? Could we schedule a call?"
        ),
        "channel": "email"
    }

    print(f"  📨 Prospect: \"{reply_data['message'][:80]}...\"")
    print()

    resp = await client.post(f"{BASE_URL}/prospects/{prospect_id}/reply", json=reply_data)
    reply = resp.json()

    print(f"  🏷️  Classification: {reply.get('reply_class', 'N/A')}")
    print(f"  📊 New State: {reply.get('state', 'N/A')}")
    print(f"  📞 Book Call: {reply.get('should_book_call', 'N/A')}")
    print(f"  👤 Human Handoff: {reply.get('needs_human_handoff', 'N/A')}")
    agent_text = reply.get("reply", "")
    if agent_text:
        print(f"\n  🤖 Agent Reply:")
        print(f"  {'─'*50}")
        for line in agent_text.split("\n"):
            print(f"  {line}")
        print(f"  {'─'*50}")
    time.sleep(PAUSE)

    # ── STEP 7: Booking ─────────────────────────────────────
    banner("STEP 7: DISCOVERY CALL BOOKING")
    narrate("Prospect confirms — booking discovery call...")

    booking_msg = {
        "prospect_id": prospect_id,
        "message": "Yes, let's do it! I'm free Tuesday or Wednesday afternoon next week.",
        "channel": "email"
    }

    print(f"  📨 Prospect: \"{booking_msg['message']}\"")
    print()

    resp = await client.post(f"{BASE_URL}/prospects/{prospect_id}/reply", json=booking_msg)
    booking = resp.json()

    print(f"  📊 State: {booking.get('state', 'N/A')}")
    print(f"  📞 Book Call: {booking.get('should_book_call', 'N/A')}")
    agent_text = booking.get("reply", "")
    if agent_text:
        print(f"\n  🤖 Agent Reply:")
        print(f"  {'─'*50}")
        for line in agent_text.split("\n"):
            print(f"  {line}")
        print(f"  {'─'*50}")
    time.sleep(PAUSE)

    # ── STEP 8: Final State + HubSpot ───────────────────────
    banner("STEP 8: HUBSPOT CONTACT RECORD")
    narrate("All data synced to HubSpot in real time throughout the flow...")

    resp = await client.get(f"{BASE_URL}/prospects/{prospect_id}")
    final = resp.json()

    print(f"  🆔 ID: {final.get('id')}")
    print(f"  🏢 Company: {final.get('company_name')}")
    print(f"  👤 Contact: {final.get('contact_name')} ({final.get('contact_title')})")
    print(f"  📧 Email: {final.get('contact_email')}")
    print(f"  📱 Phone: {final.get('contact_phone')}")
    print(f"  📊 State: {final.get('state')}")
    print(f"  📬 Emails Sent: {final.get('emails_sent')}")
    print(f"  🕒 Last Contact: {final.get('last_contact')}")
    print(f"  🏢 HubSpot ID: {final.get('hubspot_contact_id', 'N/A')}")

    cls = final.get("classification", {})
    if cls:
        print(f"  🎯 Segment: {cls.get('segment')}")
        print(f"  📊 Confidence: {cls.get('confidence')}")

    hs_id = final.get("hubspot_contact_id", "")
    if hs_id and not hs_id.startswith("sink"):
        print(f"\n  ✅ HubSpot contact is LIVE — open browser to verify:")
        print(f"  🔗 https://app-eu1.hubspot.com/contacts/148322728/contact/{hs_id}")
    else:
        print(f"\n  ℹ️  HubSpot contact ID: {hs_id}")
        print(f"  🔗 Search in HubSpot: https://app-eu1.hubspot.com/contacts/148322728")
        print(f"  🔍 Search for: {final.get('contact_email')}")

    # ── DONE ────────────────────────────────────────────────
    banner("DEMO COMPLETE")
    print("  ✅ Full pipeline demonstrated:")
    print("     1. Health check — HubSpot connected")
    print("     2. Enrichment — 5 signal sources")
    print("     3. Hiring signal brief — per-signal confidence")
    print("     4. Competitor gap brief — sector benchmarks")
    print("     5. Signal-grounded outreach email")
    print("     6. Reply → classification → qualification")
    print("     7. Discovery call booking")
    print("     8. HubSpot record — all fields populated")
    print(f"\n  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
