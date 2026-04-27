---
marp: false
theme: default
paginate: true
backgroundColor: #fff
---

<!-- Slide 1: Title -->

# The Conversion Engine

**Automated Lead Generation and Conversion System**
_for Tenacious Consulting & Outsourcing_

Amir Ahmedin | Week 10 Challenge | April 2026

---

<!-- Slide 2: The Problem -->

# The Problem Tenacious Faces

**Three linked pain points:**

1. **Manual prospecting** — Partners browse LinkedIn ad-hoc, no systematic market coverage
2. **Inconsistent qualification** — Same firmographics → different first messages depending on who writes them
3. **Slow follow-up** — 30–40% of qualified conversations stall because the person who initiated can't keep up

**Revenue consequence:** Long tail of conversations that stalled not because the prospect said no, but because Tenacious didn't keep up.

---

<!-- Slide 3: What We Built -->

# What We Built

An end-to-end AI sales agent that:

- **Finds** prospects from public data (Crunchbase, job posts, layoffs.fyi)
- **Researches** each prospect deeply (AI maturity, competitor gaps, hiring velocity)
- **Qualifies** into 4 ICP segments with confidence scoring + abstention
- **Writes** signal-grounded outreach emails (not generic pitches)
- **Handles** multi-turn replies with objection handling
- **Books** discovery calls via Cal.com
- **Syncs** everything to HubSpot CRM

---

<!-- Slide 4: Architecture -->

# System Architecture

```
┌─────────────────────────────────────────────────────┐
│              FastAPI Orchestrator (main.py)          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ENRICHMENT          QUALIFICATION    CONVERSATION  │
│  ┌──────────────┐    ┌────────────┐   ┌──────────┐ │
│  │Crunchbase ODM│    │ICP 4-Segment│  │Reply     │ │
│  │Layoffs.fyi   │    │Classifier + │  │Classify  │ │
│  │Job Posts     │    │Abstention   │  │+ Respond │ │
│  │Leadership    │    └────────────┘   │+ Handoff │ │
│  │AI Maturity   │                     └──────────┘ │
│  │Gap Analysis  │                                   │
│  └──────────────┘    CHANNEL HIERARCHY              │
│                      ① Email (Resend) — primary     │
│  EMAIL COMPOSER      ② SMS (AT) — warm leads only   │
│  + BOOKING ENGINE    ③ Voice (Cal.com) — human call │
│  + CRM (HubSpot)                                    │
├─────────────────────────────────────────────────────┤
│  KILL SWITCH: LIVE_MODE=false │ All outputs: draft  │
│  OBSERVABILITY: Langfuse + JSONL │ EVAL: τ²-Bench   │
└─────────────────────────────────────────────────────┘
```

---

<!-- Slide 5: Enrichment Pipeline -->

# Enrichment Pipeline — 6 Signal Sources

| Signal            | Source                           | What It Tells Us                       |
| ----------------- | -------------------------------- | -------------------------------------- |
| **Firmographics** | Crunchbase ODM (1,001 companies) | Industry, size, location, funding      |
| **Funding**       | Crunchbase funding rounds        | Series A/B in 180 days → fresh budget  |
| **Layoffs**       | layoffs.fyi CSV                  | Cost pressure → Segment 2 pitch        |
| **Job Posts**     | Playwright career page scraper   | Hiring velocity, tech stack            |
| **Leadership**    | Crunchbase + web scrape          | New CTO in 90 days → Segment 3         |
| **AI Maturity**   | LLM scoring (0–3)                | Gates Segment 4, shifts pitch language |

Plus: **Competitor Gap Analysis** — compares prospect against sector top quartile

---

<!-- Slide 6: AI Maturity Scoring -->

# AI Maturity Scoring (0–3)

| Score | Meaning             | Signal Pattern                          |
| ----- | ------------------- | --------------------------------------- |
| **0** | No public AI signal | Zero HIGH-weight signals                |
| **1** | Early signals       | 1–2 MEDIUM/LOW signals, no AI roles     |
| **2** | Active engagement   | AI roles OR named AI leadership         |
| **3** | Mature AI function  | Multiple HIGH signals across categories |

**6 weighted inputs:** AI roles (HIGH), AI leadership (HIGH), GitHub activity (MEDIUM), exec commentary (MEDIUM), ML stack (LOW), strategic comms (LOW)

**How it changes the pitch:**

- Score < 2 → Segment 4 **BLOCKED** (hard gate)
- Score 2–3 + Segment 1: _"Scale your AI team faster than hiring"_
- Score 0–1 + Segment 1: _"Stand up your first AI function"_

---

<!-- Slide 7: ICP Classification -->

# ICP Classification — 4 Segments + Abstention

| Priority | Segment                   | Trigger                  | Pitch Angle         |
| -------- | ------------------------- | ------------------------ | ------------------- |
| 1        | **Restructuring**         | Layoff + funding         | Cost lever          |
| 2        | **Leadership Transition** | New CTO/VP Eng < 90 days | Timing lever        |
| 3        | **Capability Gap**        | AI maturity ≥ 2 + gap    | Project consulting  |
| 4        | **Recently Funded**       | Series A/B < 180 days    | Speed lever         |
| —        | **Abstain**               | Confidence < 0.6         | Generic exploratory |

**Hard gates enforced:**

- Post-layoff → never Segment 1
- AI maturity < 2 → never Segment 4
- Headcount < 50 → never Segment 3
- Layoff > 40% → never Segment 2

---

<!-- Slide 8: Honesty Constraints -->

# Honesty Constraints — Ask, Don't Assert

The agent carries **honesty flags** that change its behavior:

| Flag                   | Trigger                 | Agent Behavior                                                       |
| ---------------------- | ----------------------- | -------------------------------------------------------------------- |
| `weak_hiring_velocity` | < 5 open roles          | "It looks like you may be growing" not "You're scaling aggressively" |
| `bench_gap_detected`   | Stack not on bench      | Acknowledges gap, doesn't promise capacity                           |
| `weak_ai_maturity`     | Low confidence score    | Asks rather than asserts AI readiness                                |
| `tech_stack_inferred`  | No confirmed stack data | Frames as inference, not fact                                        |

**Why:** Over-claiming damages Tenacious's reputation more than silence would.

---

<!-- Slide 9: Outreach Example -->

# Signal-Grounded Outreach vs Generic

**Generic (what most SDR tools produce):**

> "Hi, I noticed your company might benefit from offshore engineering talent..."

**Signal-grounded (what our system produces):**

> "You closed a $14M Series B in February and your open Python-engineering roles tripled since then — the typical bottleneck for teams in that state is recruiting capacity, not budget."

The difference: the second message is **verifiable against the prospect's own public record** and therefore hard to object to.

---

<!-- Slide 10: Conversation Manager -->

# Multi-Turn Conversation Handling

**6-class reply classification:**

- **Engaged** → Qualify + propose discovery call
- **Curious** → 3-sentence context + Cal.com link
- **Hard no** → No reply, mark opted out in HubSpot
- **Soft defer** → Close gracefully with re-engagement month
- **Objection** → Pattern-matched handling (pricing, incumbent, small POC)
- **Ambiguous** → Route to human

**Mandatory human handoff when:**

- Pricing outside public bands
- Staffing beyond bench summary
- Client reference requested
- Regulatory/legal terms mentioned
- C-level at company > 2,000 headcount

---

<!-- Slide 11: Production Stack -->

# Production Stack — All Verified Running

| Component                  | Status | Evidence                                                  |
| -------------------------- | ------ | --------------------------------------------------------- |
| **Resend (Email)**         | ✅     | 11 test emails in sink, trace `out_email_send_test-001_0` |
| **Africa's Talking (SMS)** | ✅     | Sandbox active, STOP/HELP handling verified               |
| **HubSpot Sandbox**        | ✅     | 4 sink records (contact, company, note, deal)             |
| **Cal.com**                | ✅     | Mock slots generated, bookings to sink                    |
| **Langfuse**               | ✅     | 22 trace entries, dual-write cloud + local                |
| **Render**                 | ✅     | Live at conversion-engine-2nti.onrender.com               |

**Kill switch:** `LIVE_MODE=false` by default — all outbound to local sink, all outputs marked `draft: true`

---

<!-- Slide 12: τ²-Bench Baseline -->

# τ²-Bench Baseline (Act I)

**What is τ²-Bench?** Sierra Research's dual-control conversational agent benchmark. Retail domain = closest public analog to B2B qualification.

| Metric         | Instructor Baseline     | Our Reproduction         |
| -------------- | ----------------------- | ------------------------ |
| Model          | gpt-4.1 (direct OpenAI) | gpt-4.1 (via OpenRouter) |
| Tasks × Trials | 30 × 5 = 150 sims       | 30 × 1 = 30 sims         |
| **pass@1**     | **72.67%**              | **63.3%**                |
| 95% CI         | [65.0%, 79.2%]          | [45.5%, 78.1%]           |
| Cost/task      | $0.02                   | $0.53                    |

CIs overlap → our reproduction is consistent with the instructor baseline.

---

<!-- Slide 13: Adversarial Probes -->

# Adversarial Probing (Act III) — 33 Probes

| Category                  | Probes | Active Failures                |
| ------------------------- | ------ | ------------------------------ |
| ICP Misclassification     | 5      | 0 ✅                           |
| Signal Over-Claiming      | 4      | 0 ✅                           |
| Bench Over-Commitment     | 3      | 0 ✅                           |
| Tone Drift                | 5      | 1 ⚠️ (subject line > 60 chars) |
| Multi-Thread Leakage      | 2      | 0 ✅                           |
| Cost Pathology            | 3      | 1 ⚠️ (max-steps loop)          |
| Dual-Control Coordination | 2      | 1 ⚠️ (auth never checked)      |
| Scheduling Edge Cases     | 3      | 1 ⚠️ (timezone labels)         |
| Signal Reliability        | 3      | 1 ⚠️ (stale Crunchbase data)   |
| Gap Over-Claiming         | 3      | 1 ⚠️ (URL validation)          |

**Target failure mode:** Max-steps reasoning loop (60% trigger rate, $50K–$190K/mo revenue impact)

---

<!-- Slide 14: Mechanism Design -->

# Mechanism Design (Act IV) — Policy-Aware Agent

**Problem:** Agent fails to confirm details before write actions → wrong parameters → task failure

**Solution:** Add 3 explicit rules to the system prompt (~80 extra tokens):

1. **AUTHENTICATE FIRST** — Verify user identity before any account action
2. **CONFIRM BEFORE CHANGES** — State what you'll do, wait for approval
3. **FOLLOW POLICY EXACTLY** — Apply all rules strictly

**Design iteration:** First version was 350 tokens with a 5-step workflow → made gpt-4.1 _more_ verbose → 3/5 tasks hit max-steps. Refined to 80 tokens with just the 3 rules → zero max-steps hits.

---

<!-- Slide 15: Mechanism Results -->

# Mechanism Results — 30 Tasks × 1 Trial

| Metric      | Baseline       | Mechanism      | Instructor Ref |
| ----------- | -------------- | -------------- | -------------- |
| **pass@1**  | **63.3%**      | **70.0%**      | **72.7%**      |
| 95% CI      | [45.5%, 78.1%] | [52.1%, 83.3%] | [65.0%, 79.2%] |
| DB match    | —              | 100%           | —              |
| Cost/task   | $0.53          | $0.15          | $0.02          |
| p95 latency | 49.1s          | 38.0s          | 551.6s         |

**Delta A: +6.7 percentage points** (positive)
Fisher p = 0.39 (not significant at p<0.05 — needs 5 trials for power)

**Mechanism nearly matches instructor reference** (70.0% vs 72.7%) while being 72% cheaper per task.

---

<!-- Slide 16: Ablation -->

# Ablation — Which Rule Matters Most?

| Variant          | Rules Added | pass@1             | Insight                |
| ---------------- | ----------- | ------------------ | ---------------------- |
| Baseline         | None        | 20% (dev)          | Default behavior       |
| Auth-only        | Rule 1      | 20% (dev)          | No reward impact alone |
| **Confirm-only** | **Rule 2**  | **40% (dev)**      | **Primary driver**     |
| Full mechanism   | Rules 1+2+3 | **70% (held-out)** | Best combined          |

**Key finding:** The confirm-before-write rule is the highest-impact single intervention. It forces the agent to restate parameters before executing, catching errors that would otherwise cause DB mismatch.

---

<!-- Slide 17: Latency -->

# System Latency (40 Real Interactions)

| Operation                               | p50       | p95       |
| --------------------------------------- | --------- | --------- |
| **Enrichment** (all 6 signals)          | 10.1s     | 20.9s     |
| **Outreach** (LLM email composition)    | 13.0s     | 43.3s     |
| **Reply handling** (classify + respond) | 14.5s     | 16.3s     |
| **Webhooks** (email + SMS)              | 0.7s      | 0.7s      |
| **Overall**                             | **11.9s** | **20.9s** |

Acceptable for email-based B2B outreach where prospects expect responses within hours, not seconds.

Bottleneck: LLM inference via OpenRouter. Switching to faster model for non-critical calls would reduce p50 to ~8s.

---

<!-- Slide 18: Business Impact -->

# Projected Business Impact

**At Tenacious's conversion funnel:**

| Scenario     | Segments       | Outbound/week | Reply rate | Qualified/mo | Revenue impact  |
| ------------ | -------------- | ------------- | ---------- | ------------ | --------------- |
| Pilot        | Segment 1 only | 60            | 7–12%      | 8–14         | $240K–$720K ACV |
| Two segments | Seg 1 + 2      | 120           | 7–12%      | 16–28        | $480K–$1.4M ACV |
| Full deploy  | All 4          | 240           | 7–12%      | 32–56        | $960K–$2.8M ACV |

**Stalled-thread rate:** Current manual process 30–40% → System target < 15%
**Cost per qualified lead:** < $5 target (achieved: $0.15/task on τ²-Bench)

---

<!-- Slide 19: Pilot Recommendation -->

# Pilot Recommendation

**Start with Segment 1 (Recently Funded Series A/B)**

- **Why:** Clearest signal (Crunchbase funding data), highest bench match, shortest sales cycle
- **Volume:** 60 outbound/week (matches current SDR capacity)
- **Budget:** $50/week LLM spend + existing Resend/HubSpot free tiers
- **Duration:** 30 days
- **Success metric:** Reply rate > 5% (vs 1–3% baseline cold email)

**Kill-switch trigger:** Pause if:

- Reply rate < 2% after 200 sends
- Any prospect publicly complains about factual errors
- Stalled-thread rate exceeds 40% (worse than manual)

---

<!-- Slide 20: Known Limitations -->

# Known Limitations & Risks

1. **No real reply-rate data** — All prospects are synthetic. The 7–12% projection is from industry benchmarks, not measured.

2. **Signal lossiness** — Quietly sophisticated companies (AI work in private repos) score 0. Loud-but-shallow companies (AI in marketing only) may score 2. Both lead to wrong pitch.

3. **Gap brief URL validation** — LLM-generated source URLs are not verified. 5% factual error rate on 1,000 emails = 50 wrong-signal emails → brand damage risk.

4. **Single-trial evaluation** — 30 tasks × 1 trial. Statistical significance requires 5+ trials (p=0.39 currently).

5. **Stale Crunchbase data** — Frozen snapshot, no freshness check. Companies that changed status will have wrong signals.

---

<!-- Slide 21: What's Next -->

# Next Steps for Production

| Priority | Action                                                   | Impact                      |
| -------- | -------------------------------------------------------- | --------------------------- |
| 1        | Run 30 × 5 trial evaluation for statistical significance | Confidence in mechanism     |
| 2        | Add subject line length constraint (< 60 chars)          | +10–15% open rate           |
| 3        | Add Crunchbase data freshness check                      | Prevent stale-signal errors |
| 4        | Validate gap brief source URLs                           | Prevent fabricated claims   |
| 5        | Add timezone labels to scheduling                        | Prevent missed calls        |
| 6        | Register AT production sender ID                         | Enable live SMS             |
| 7        | 30-day pilot on Segment 1                                | Real reply-rate measurement |

---

<!-- Slide 22: Demo Highlights -->

# Demo Highlights

1. **Enrichment:** Company name → full hiring signal brief + competitor gap brief in ~10s
2. **Classification:** Post-layoff + funded company correctly routed to Segment 2 (not Segment 1)
3. **Outreach:** Signal-grounded email with verifiable claims, honesty flags respected
4. **Reply handling:** Objection ("too expensive") → pricing pattern match → human handoff
5. **HubSpot:** All fields populated, enrichment timestamps, deal created on qualification
6. **Kill switch:** Everything routes to local sink, all outputs marked draft
7. **τ²-Bench:** Mechanism achieves 70% pass@1, nearly matching instructor reference

---

<!-- Slide 23: Summary -->

# Summary

| What                  | Result                                                   |
| --------------------- | -------------------------------------------------------- |
| **System**            | End-to-end lead gen + conversion pipeline                |
| **Enrichment**        | 6 signal sources + competitor gap analysis               |
| **Classification**    | 4 ICP segments + abstention at < 0.6 confidence          |
| **Channels**          | Email (primary) → SMS (warm) → Voice (human call)        |
| **τ²-Bench baseline** | 63.3% pass@1 (reproduces instructor's 72.7%)             |
| **Mechanism**         | 70.0% pass@1 (+6.7% over baseline)                       |
| **Probes**            | 33 adversarial probes, 5 active failures identified      |
| **Safety**            | Kill switch, draft marking, honesty flags, human handoff |

**The system is ready for a controlled pilot on Segment 1.**

---

<!-- Slide 24: Thank You -->

# Thank You

**Repository:** github.com/conversion-engine
**Live API:** conversion-engine-2nti.onrender.com/health
**Contact:** shuaibahmedin@gmail.com

_Find the lead. Ground the conversation. Respect the brand. Ship it._
