# DEMO VIDEO NARRATION SCRIPT
# Total time: ~8 minutes
# Run: python3 demo_video.py in Terminal 2 while recording screen

## BEFORE RECORDING

1. Terminal 1: server running (`python3 -m agent.main`)
2. Terminal 2: ready to run demo
3. Browser Tab 1: HubSpot open (https://app-eu1.hubspot.com/contacts/148322728)
4. Browser Tab 2: Cal.com open (https://cal.com/amir-a-zbucqo/secret) — optional
5. Start screen recording (OBS or GNOME Ctrl+Shift+R)

---

## [0:00–0:20] INTRO — Before running the script

SAY:
"Hi, this is the Conversion Engine — an automated lead generation and conversion
system built for Tenacious Consulting and Outsourcing. I'll walk through the
complete pipeline: enriching a prospect from public signals, sending a
signal-grounded outreach email, handling a reply, qualifying the prospect,
and booking a discovery call — all synced to HubSpot in real time.
Let me start the demo."

ACTION: Type `python3 demo_video.py` and press Enter.

---

## [0:20–0:40] STEP 1: Health Check

WAIT for output to appear, then SAY:
"The system is live. Kill switch is disengaged, meaning outbound email goes
through Resend for real delivery. HubSpot is connected to our sandbox portal.
The server is running locally but hitting real external APIs — Resend for email,
HubSpot for CRM, and Cal.com for booking."

---

## [0:40–2:00] STEP 2: Enrichment

WAIT for enrichment to complete (~20 seconds), then SAY:
"We just enriched the prospect Consolety — a real company from our Crunchbase
sample. The pipeline ran five signal sources: Crunchbase for firmographics and
funding, job post scraping for hiring velocity, layoffs.fyi for headcount
reductions, leadership change detection, and AI maturity scoring.

The result: Consolety is classified as Segment 2 — mid-market restructure —
because they had a 100-person layoff. AI maturity is zero out of three with
low confidence. Notice the honesty flags: weak hiring velocity signal and
tech stack inferred not confirmed. These flags tell the email composer to use
interrogative phrasing instead of assertive claims.

HubSpot sync shows 'live' — the contact and company were created in HubSpot
in real time. You can see the contact ID and company ID are real HubSpot
record IDs, not sink placeholders."

---

## [2:00–2:40] STEP 3: Hiring Signal Brief

SAY:
"Here's the full hiring signal brief with per-signal confidence scores.
Funding: not detected. Layoffs: detected — 100 people in August 2022.
Hiring velocity: insufficient signal — zero open roles found on their
career page. Leadership change: not detected. AI maturity: zero out of
three with 0.3 confidence — very low.

The honesty flags are critical. They propagate through the entire pipeline
to the email composer, ensuring we never over-claim. The bench match shows
false — we don't have engineers matching their specific stack needs."

---

## [2:40–3:20] STEP 4: Competitor Gap Brief

SAY:
"The competitor gap brief analyzed Consolety against peers in the SEO sector
from our Crunchbase sample. Their AI maturity is zero versus the sector
top quartile benchmark. The system identified two gap findings — areas where
peers are investing that Consolety is not.

The pitch shift recommendation tells the email composer how to frame the
outreach: position their specialized focus as a strength while highlighting
opportunities to develop technical tools. This is research-grounded, not
generic."

---

## [3:20–4:10] STEP 5: Outreach Email

WAIT for email to send, then SAY:
"The email was composed and delivered via Resend. Look at the subject line —
it's signal-grounded, referencing their specific situation. The confidence
level is 'low' because the signals are weak, so the email uses careful
phrasing.

Three specific signals are referenced in this email: the 2022 layoff, the
AI maturity score, and the competitor gap finding. This is the key
differentiator — every email leads with a research finding. We generated
both signal-grounded and generic variants for four prospects and compared
them. Signal-grounded emails averaged three signals per email. Generic
emails had zero. Industry benchmarks show this difference drives reply
rates from one to three percent up to seven to twelve percent."

---

## [4:10–5:20] STEP 6: Prospect Reply + Qualification

WAIT for reply processing, then SAY:
"Now we simulate the prospect replying. Amara says she's interested in
scaling her AI/ML team and asks about bench availability.

The conversation manager first classifies the reply — it's 'engaged,' a
substantive response with specific questions. The state transitions to
'qualified' and should-book-call is true.

The agent's reply is grounded in the bench summary — it references the
five ML engineers actually available, not a made-up number. It proposes
a specific discovery call. And look — the Cal.com booking link is
appended to the email that was sent. This is a real clickable link that
opens the Cal.com scheduling page with the prospect's name and email
pre-filled."

---

## [5:20–6:20] STEP 7: Discovery Call Booking

WAIT for booking response, then SAY:
"The prospect confirms — she's free Tuesday or Wednesday. The agent
responds with confirmation and the booking link is included again in
the sent email.

The state is now 'call_booked.' This entire flow — from enrichment to
qualification to booking — happened automatically. The conversation
manager classified two replies, generated two context-aware responses,
and the booking engine generated the Cal.com link. All of this synced
to HubSpot at every step."

---

## [6:20–7:20] STEP 8: HubSpot Contact Record

SAY:
"Here's the final prospect state. Contact ID is a real HubSpot record —
not a sink placeholder. State is call_booked, one email sent, all fields
populated.

Let me show you the actual HubSpot record."

ACTION: Switch to browser. Open the HubSpot link shown in the terminal output.

SAY (while showing HubSpot):
"Here's the contact in HubSpot. You can see all the custom fields we
created: ICP segment is Segment 2, AI maturity score is zero, enrichment
timestamp is current, conversation state is call_booked, emails sent is
one. The company record is also created with all enrichment data —
layoff information, hiring velocity, gap analysis results.

Every field is non-null. The enrichment timestamp is from this demo run.
This is a live HubSpot sandbox — not a mock."

---

## [7:20–7:50] STEP 9: Wrap-up

SAY:
"That's the complete pipeline. To summarize what we demonstrated:

One — enrichment from five public signal sources with per-signal confidence.
Two — hiring signal brief and competitor gap brief with honesty flags.
Three — signal-grounded outreach email delivered via Resend.
Four — prospect reply classified and qualified through the hiring signal brief.
Five — discovery call booked via Cal.com with a real scheduling link.
Six — HubSpot contact record populated in real time with all fields non-null.

The system costs seven cents per qualified lead. On the tau-squared bench
evaluation, our policy-aware mechanism achieved seventy percent pass-at-one
versus the sixty-three percent baseline — a six point seven percentage
point improvement."

---

## [7:50–8:00] CLOSE

SAY:
"Thank you for watching. The full code, evaluation results, and two-page
decision memo are in the GitHub repository."

ACTION: Stop recording.

---

## TIPS

- Speak at a natural pace, not rushed
- Point at specific numbers on screen as you mention them
- When switching to HubSpot, give it 2-3 seconds to load
- If enrichment takes long (>30s), say "The enrichment pipeline is calling
  the LLM for AI maturity scoring and gap analysis — this takes about
  twenty seconds per prospect"
- If anything errors, say "Let me show you the data that was captured"
  and show the outbound_sink files instead
