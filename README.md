# The Conversion Engine

Automated Lead Generation and Conversion System for Tenacious Consulting and Outsourcing.

## Architecture

```
                         ┌──────────────────────┐
                         │   FastAPI Orchestrator│
                         │      (main.py)        │
                         └──────┬───────────────┘
                                │
          ┌─────────────┬───────┼────────┬──────────────┐
          ▼             ▼       ▼        ▼              ▼
   ┌────────────┐ ┌──────────┐ ┌──────┐ ┌──────────┐ ┌───────┐
   │ Enrichment │ │Qualifier │ │Email │ │Conversation│ │Booking│
   │  Pipeline  │ │ (ICP)    │ │+SMS  │ │  Manager  │ │Engine │
   └─────┬──────┘ └────┬─────┘ └──┬───┘ └─────┬─────┘ └──┬────┘
         │              │          │            │          │
   ┌─────┴──────┐       │     ┌───┴────┐       │     ┌───┴────┐
   │Crunchbase  │       │     │Resend/ │       │     │Cal.com │
   │Job Posts   │       │     │MailSend│       │     │  API   │
   │Layoffs.fyi │       │     │AT SMS  │       │     └────────┘
   │AI Maturity │       │     └────────┘       │
   │Gap Analysis│       │                      │
   └────────────┘       │               ┌──────┴──────┐
                        │               │  HubSpot    │
                        └───────────────│  MCP/API    │
                                        └─────────────┘
   ┌─────────────────────────────────────────────────────┐
   │  Observability: Langfuse  │  Eval: τ²-Bench        │
   └─────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Create venv and install
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.template .env
# Edit .env with your API keys

# 3. Run enrichment pipeline on a test prospect
python -m agent.enrichment.pipeline --company "Example Corp"

# 4. Run the full server
python -m agent.main

# 5. Run τ²-Bench baseline
python -m eval.harness --mode baseline
```

## Project Structure

```
agent/           - Core agent source
  enrichment/    - Signal collection (Crunchbase, jobs, layoffs, AI maturity, gap analysis)
  qualification/ - ICP segment classifier with abstention
  outreach/      - Email composer + SMS handler
  conversation/  - Multi-turn thread manager
  booking/       - Cal.com integration
eval/            - τ²-Bench harness, score logs, traces
probes/          - Adversarial probe library
seed_data/       - ICP definition, style guide, pricing, bench summary
config/          - Configuration and environment
data/            - Raw data (Crunchbase ODM, layoffs.fyi, job posts)
scripts/         - Setup and utility scripts
```

## Kill Switch

The system defaults to `LIVE_MODE=false`. All outbound routes to local log sink.
Set `LIVE_MODE=true` only after Tenacious executive approval.

## Data Handling

- No real customer data is used
- All prospects during development are synthetic
- Seed materials are draft-only and not redistributable
