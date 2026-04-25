# The Conversion Engine

Automated Lead Generation and Conversion System for Tenacious Consulting and Outsourcing.

## Architecture

```
                         ┌──────────────────────────┐
                         │   FastAPI Orchestrator    │
                         │   agent/main.py           │
                         │   POST /prospects/enrich  │
                         │   POST /prospects/:id/    │
                         │        outreach           │
                         │   POST /prospects/:id/    │
                         │        reply              │
                         │   GET  /health            │
                         └──────────┬───────────────┘
                                    │
          ┌──────────────┬──────────┼──────────┬──────────────┐
          ▼              ▼          ▼          ▼              ▼
   ┌─────────────┐ ┌──────────┐ ┌───────┐ ┌───────────┐ ┌────────┐
   │ Enrichment  │ │Qualifier │ │Email  │ │Conversation│ │Booking │
   │ Pipeline    │ │(ICP)     │ │+ SMS  │ │ Manager    │ │Engine  │
   │             │ │          │ │       │ │            │ │        │
   │ pipeline.py │ │classifier│ │sender │ │ manager.py │ │engine  │
   │             │ │.py       │ │.py    │ │            │ │.py     │
   └──────┬──────┘ └────┬─────┘ └───┬───┘ └─────┬──────┘ └───┬────┘
          │              │           │            │            │
   ┌──────┴──────┐       │      ┌────┴────┐      │      ┌─────┴────┐
   │ 5 Signal    │       │      │ Resend  │      │      │ Cal.com  │
   │ Sources:    │       │      │ (email) │      │      │ API      │
   │             │       │      │         │      │      └──────────┘
   │ crunchbase  │       │      │ AT SMS  │      │
   │ .py         │       │      │ (warm   │      │
   │             │       │      │  leads  │      │
   │ job_posts   │       │      │  only)  │      │
   │ .py         │       │      └─────────┘      │
   │             │       │                       │
   │ layoffs.py  │       │                ┌──────┴──────┐
   │             │       │                │  HubSpot    │
   │ leadership  │       │                │  CRM API    │
   │ .py         │       └────────────────│  hubspot.py │
   │             │                        └─────────────┘
   │ ai_maturity │
   │ .py         │
   │             │
   │ gap_analysis│
   │ .py         │
   └─────────────┘

   ┌─────────────────────────────────────────────────────────┐
   │  Observability: Langfuse (tracer.py)                    │
   │  Evaluation:    τ²-Bench (eval/harness.py)              │
   │  Kill Switch:   LIVE_MODE=false → all outbound to sink  │
   └─────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Enrich** → `POST /prospects/enrich` → runs 5 signal sources (Crunchbase firmographics + funding, job-post velocity, layoffs.fyi, leadership detection, AI maturity scoring) + competitor gap analysis → classifies into ICP segment → syncs to HubSpot
2. **Outreach** → `POST /prospects/:id/outreach` → composes signal-grounded email using enrichment data + style guide → sends via Resend (live) or local sink
3. **Reply** → `POST /prospects/:id/reply` → classifies reply (engaged/curious/hard_no/soft_defer/objection/ambiguous) → generates context-aware response → updates HubSpot → books call if qualified
4. **Booking** → Cal.com integration for discovery call scheduling → syncs booking to HubSpot contact record

## Setup

```bash
# 1. Clone and create venv
git clone <repo-url>
cd 10Acweek10
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.template .env
# Edit .env with your API keys:
#   OPENROUTER_API_KEY  — LLM calls (enrichment, composition, conversation)
#   RESEND_API_KEY      — email delivery
#   AT_API_KEY          — SMS (Africa's Talking sandbox)
#   HUBSPOT_ACCESS_TOKEN — CRM sync
#   CALCOM_API_KEY      — booking
#   LANGFUSE keys       — observability

# 3. Create HubSpot custom properties (run once)
python3 -m agent.main &
curl -X POST http://localhost:8000/hubspot/setup

# 4. Run enrichment pipeline on a test prospect
python3 -m agent.enrichment.pipeline --company "Example Corp"

# 5. Run the full server
python3 -m agent.main

# 6. Run the demo (in a second terminal)
python3 demo_video.py

# 7. Run τ²-Bench evaluation
cd tau2-bench && source .venv/bin/activate && cd ..
python3 eval/act4_runner.py --mode dev
```

## Directory Index

```
agent/                          Core agent source code
  main.py                       FastAPI orchestrator — all API endpoints
  models.py                     Pydantic models (Prospect, HiringSignalBrief,
                                CompetitorGapBrief, AIMaturityScore, etc.)
  llm_client.py                 OpenRouter LLM client wrapper
  enrichment/                   Signal collection pipeline
    pipeline.py                 Orchestrates all 5 signal sources + gap analysis
    crunchbase.py               Crunchbase ODM: firmographics + funding signals
    job_posts.py                Career page scraper: role counts, velocity, stacks
    layoffs.py                  Layoffs.fyi CSV parser: headcount, date, recency
    leadership.py               Leadership change detector (Crunchbase + web scrape)
    ai_maturity.py              AI maturity scorer (0-3, 6 weighted inputs, LLM)
    gap_analysis.py             Competitor gap brief generator (LLM)
  qualification/
    classifier.py               ICP segment classifier with abstention logic
  outreach/
    email_composer.py            Signal-grounded email composition (LLM)
    email_sender.py              Resend integration + local sink fallback
    sms_handler.py               Africa's Talking SMS with warm-lead gate
  conversation/
    manager.py                   Multi-turn thread manager with reply classification
  booking/
    engine.py                    Cal.com booking integration
  crm/
    hubspot.py                   HubSpot CRM: contacts, companies, deals, notes
  observability/
    tracer.py                    Langfuse tracing + local trace log

eval/                           Evaluation and analysis
  method.md                     Mechanism design, 3 ablation variants, statistical test
  ablation_results.json         pass@1, CI, cost/task, p95 for 3 conditions
  held_out_traces.jsonl         Raw traces from baseline + mechanism + instructor ref
  evidence_graph.json           Maps every memo claim to source trace/file
  invoice_summary.json          LLM spend breakdown, cost per qualified lead
  outbound_variant_traces.jsonl Signal-grounded vs generic variant comparison
  outbound_variant_summary.json Variant comparison summary metrics
  harness.py                    τ²-Bench evaluation harness
  act4_runner.py                Mechanism vs baseline runner
  policy_aware_agent.py         Policy-aware agent implementation
  trace_log.jsonl               All pipeline and outbound traces
  score_log.json                τ²-Bench score history

probes/                         Adversarial probe library
  probe_library.md              33 structured probes across 10 categories
  failure_taxonomy.md           Probes grouped by category with trigger rates
  target_failure_mode.md        Highest-ROI failure mode with business-cost derivation

seed_data/                      Tenacious reference materials
  icp_definition.md             ICP segment definitions
  style_guide.md                Tone and language rules
  pricing_sheet.md              Public pricing bands
  bench_summary.json            Current bench availability
  baseline_numbers.md           Conversion funnel baselines
  case_studies.md               Anonymized case studies
  email_sequences/              Cold, warm, re-engagement templates
  discovery_transcripts/        5 annotated discovery call transcripts
  schemas/                      hiring_signal_brief + competitor_gap_brief schemas
  policy/                       Data handling policy + acknowledgement

config/
  settings.py                   Pydantic settings from .env

data/
  crunchbase/                   Crunchbase ODM sample (1,000 companies)
  layoffs/                      Layoffs.fyi CSV
  job_posts/                    Cached career page scrapes
  outbound_sink/                Local sink for emails, SMS, bookings, HubSpot
```

## Kill Switch

The system defaults to `LIVE_MODE=false`. All outbound (email, SMS, bookings) routes to `data/outbound_sink/` as JSON files. HubSpot syncs regardless of mode (uses sandbox portal).

Set `LIVE_MODE=true` and `OUTBOUND_SINK=resend` only for demo recording or after Tenacious executive approval.

## Limitations and Next Steps

**Known limitations (for the inheriting engineer):**

1. **No real reply-rate measurement.** All prospects are synthetic. The 7–12% reply-rate projection is from industry benchmarks, not measured. The pilot must track actual reply rates.
2. **Single-trial evaluation.** τ²-Bench mechanism results (70.0% pass@1) are from 1 trial per task. Statistical significance requires 5+ trials (p=0.39 currently).
3. **Subject line length.** The LLM generates >60-char subjects (Probe 4.5). Needs a post-generation length check with re-prompting.
4. **Stale Crunchbase data.** The ODM sample is a frozen snapshot. No freshness check on records. Companies that changed status after the snapshot will have stale signals.
5. **Job scraper requires Playwright.** Career page scraping depends on Playwright browser automation. Some JS-heavy career pages (Greenhouse, Lever iframes) may not render correctly.
6. **SMS sandbox only.** Africa's Talking is configured for sandbox mode. Production SMS requires AT production credentials and sender ID registration.
7. **Cal.com booking is mock in safe mode.** Real bookings require `LIVE_MODE=true` and a valid Cal.com event type.

**Next steps for production:**

1. Add a 60-day job-post velocity delta by storing historical scrape snapshots and computing `(roles_today - roles_60d_ago) / roles_60d_ago`
2. Add Crunchbase data freshness check — flag records older than 6 months
3. Implement subject line length constraint (re-prompt if >60 chars)
4. Add URL validation for competitor gap brief source URLs
5. Run 30-task × 5-trial evaluation for statistical significance
6. Register Africa's Talking production sender ID for live SMS
7. Add webhook signature verification for Resend and Cal.com callbacks

## Data Handling

- No real customer data is used
- All prospects during development are synthetic
- Seed materials are draft-only and not redistributable
- See `seed_data/policy/data_handling_policy.md` for full policy
