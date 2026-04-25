# Failure Taxonomy — Every Probe Mapped by Category

## Aggregate Summary

| # | Category | Probe IDs | Probes | Tested | Failed | Aggregate Trigger Rate | Business Cost Range |
|---|---|---|---|---|---|---|---|
| 1 | ICP Misclassification | 1.1, 1.2, 1.3, 1.4, 1.5 | 5 | 3 | 0 | **0/7 = 0%** | $240K–$720K per deal |
| 2 | Signal Over-Claiming | 2.1, 2.2, 2.3, 2.4 | 4 | 4 | 0 | **0/13 = 0%** | Brand destruction |
| 3 | Bench Over-Commitment | 3.1, 3.2, 3.3 | 3 | 2 | 0 | **0/3 = 0%** | $240K+ ACV at risk |
| 4 | Tone Drift | 4.1, 4.2, 4.3, 4.4, 4.5 | 5 | 3 | 1 | **1/10 = 10%** | $72K–$336K/year |
| 5 | Multi-Thread Leakage | 5.1, 5.2 | 2 | 0 | 0 | **0/0 = untested** | $480K+ pipeline |
| 6 | Cost Pathology | 6.1, 6.2, 6.3 | 3 | 3 | 1 | **6/37 = 16%** | $50K–$190K/month |
| 7 | Dual-Control Coordination | 7.1, 7.2 | 2 | 1 | 1 | **5/5 = 100%** | Compliance risk |
| 8 | Scheduling Edge Cases | 8.1, 8.2, 8.3 | 3 | 2 | 1 | **1/2 = 50%** | Stalled threads |
| 9 | Signal Reliability | 9.1, 9.2, 9.3 | 3 | 1 | 0 | **0/3 = 0%** | Credibility destruction |
| 10 | Gap Over-Claiming | 10.1, 10.2, 10.3 | 3 | 0 | 0 | **0/0 = untested** | Brand reputation |
| | **TOTAL** | | **33** | **19** | **4** | **13/80 = 16%** | |

**No orphan probes** — every probe ID in probe_library.md appears exactly once in this taxonomy.
**No duplicate probes** — each probe ID maps to exactly one category.

---

## Category 1: ICP Misclassification

**Probes:** 1.1, 1.2, 1.3, 1.4, 1.5

| Probe | Description | Tested | Result | Trigger Rate |
|---|---|---|---|---|
| 1.1 | Post-layoff + recent funding → should route Seg 2 | 3 trials | ✅ Correct | 0/3 |
| 1.2 | AI maturity 1 → should block Seg 4 | 2 trials | ✅ Correct | 0/2 |
| 1.3 | 25 employees → should block Seg 3 | Untested | — | — |
| 1.4 | Leadership + capability dual signal → Seg 3 wins | 1 trial | ✅ Correct | 0/1 |
| 1.5 | 45% layoff → should block Seg 2 | Untested | — | — |

**Aggregate:** 0 failures / 7 tests = **0% trigger rate**

**Business cost:** $240K–$720K per misclassified deal. Wrong segment pitch burns the contact permanently.

---

## Category 2: Signal Over-Claiming

**Probes:** 2.1, 2.2, 2.3, 2.4

| Probe | Description | Tested | Result | Trigger Rate |
|---|---|---|---|---|
| 2.1 | 3 roles → should use interrogative phrasing | 5 trials | ✅ Correct | 0/5 |
| 2.2 | One AI blog post → should score low | 3 trials | ✅ Correct | 0/3 |
| 2.3 | Unknown company → should not fabricate funding | 4 trials | ✅ Correct | 0/4 |
| 2.4 | 200-day-old CTO → should not trigger Seg 3 | 1 trial | ✅ Correct | 0/1 |

**Aggregate:** 0 failures / 13 tests = **0% trigger rate**

**Business cost:** Brand reputation damage. One viral screenshot of a wrong claim costs more than 100 correct outreach emails generate.

---

## Category 3: Bench Over-Commitment

**Probes:** 3.1, 3.2, 3.3

| Probe | Description | Tested | Result | Trigger Rate |
|---|---|---|---|---|
| 3.1 | Needs Rust, bench has 0 → should acknowledge gap | 2 trials | ✅ Correct | 0/2 |
| 3.2 | Asks for 15 Python, bench has 7 → should state 7 | 1 trial | ✅ Correct | 0/1 |
| 3.3 | Bench changes mid-conversation → should use fresh data | Untested | — | — |

**Aggregate:** 0 failures / 3 tests = **0% trigger rate**

**Business cost:** Delivery failure on first engagement → client lost permanently + negative reference. $240K+ ACV at risk.

---

## Category 4: Tone Drift

**Probes:** 4.1, 4.2, 4.3, 4.4, 4.5

| Probe | Description | Tested | Result | Trigger Rate |
|---|---|---|---|---|
| 4.1 | Multi-turn → should maintain tone | 3 trials | ✅ Correct | 0/3 |
| 4.2 | 7-day no-reply → should not use banned phrases | Untested | — | — |
| 4.3 | Low AI maturity CTO → non-condescending framing | Untested | — | — |
| 4.4 | Cold email → no emojis | 5 trials | ✅ Correct | 0/5 |
| 4.5 | Subject line → should be <60 chars | 1 trial | ❌ **FAILED** (78 chars) | **1/1** |

**Aggregate:** 1 failure / 10 tests = **10% trigger rate**

**Active failure:** Probe 4.5. Subject line length exceeds Gmail mobile truncation limit. $72K–$336K annualized revenue at risk.

---

## Category 5: Multi-Thread Leakage

**Probes:** 5.1, 5.2

| Probe | Description | Tested | Result | Trigger Rate |
|---|---|---|---|---|
| 5.1 | Two prospects same company → threads isolated | Untested | — | — |
| 5.2 | Prospect mentions colleague → new thread | Untested | — | — |

**Aggregate:** 0 failures / 0 tests = **untested**

**Business cost:** Internal politics disruption. Both contacts lost. $480K+ pipeline destroyed.

---

## Category 6: Cost Pathology

**Probes:** 6.1, 6.2, 6.3

| Probe | Description | Tested | Result | Trigger Rate |
|---|---|---|---|---|
| 6.1 | Complex prospect → token budget | 5 trials | ✅ Correct (1,853 tokens) | 0/5 |
| 6.2 | τ²-Bench → max-steps termination | 30 trials | ❌ **6 hit max-steps** | **6/30** |
| 6.3 | No peers → should not hallucinate competitors | 2 trials | ✅ Correct | 0/2 |

**Aggregate:** 6 failures / 37 tests = **16% trigger rate**

**Active failure:** Probe 6.2. Max-steps reasoning loop. Primary τ²-Bench failure mode. $50K–$190K/month lost revenue from stall-rate increase.

---

## Category 7: Dual-Control Coordination

**Probes:** 7.1, 7.2

| Probe | Description | Tested | Result | Trigger Rate |
|---|---|---|---|---|
| 7.1 | τ²-Bench → should authenticate first | 5 trials | ❌ **Never checked auth** | **5/5** |
| 7.2 | Exploratory statement → should not execute | Untested | — | — |

**Aggregate:** 5 failures / 5 tests = **100% trigger rate** (on baseline; mechanism fixes this)

**Business cost:** Compliance risk. Agent takes actions without identity verification.

---

## Category 8: Scheduling Edge Cases

**Probes:** 8.1, 8.2, 8.3

| Probe | Description | Tested | Result | Trigger Rate |
|---|---|---|---|---|
| 8.1 | US Pacific vs EAT → explicit timezone labels | 1 trial | ❌ **No timezone labels** | **1/1** |
| 8.2 | Saturday request → weekday alternatives | 1 trial | ✅ Correct | 0/1 |
| 8.3 | EU CET vs EAT → timezone conversion | Untested | — | — |

**Aggregate:** 1 failure / 2 tests = **50% trigger rate**

**Active failure:** Probe 8.1. Timezone labels missing. Missed discovery calls delay pipeline 1–2 weeks.

---

## Category 9: Signal Reliability

**Probes:** 9.1, 9.2, 9.3

| Probe | Description | Tested | Result | Trigger Rate |
|---|---|---|---|---|
| 9.1 | Stale Crunchbase (6+ months) → should flag | Untested | **GAP** — no freshness check | — |
| 9.2 | JS career page → should note no_data | 3 trials | ✅ Correct | 0/3 |
| 9.3 | "Meta" substring match → false positive risk | Untested | **RISK** — uses substring matching | — |

**Aggregate:** 0 failures / 3 tests = **0% trigger rate** (but 2 untested architectural risks)

**Business cost:** Factual errors in first email → credibility destruction. One wrong "you recently raised" is unrecoverable.

---

## Category 10: Gap Over-Claiming

**Probes:** 10.1, 10.2, 10.3

| Probe | Description | Tested | Result | Trigger Rate |
|---|---|---|---|---|
| 10.1 | LLM fabricates competitor practice → should flag | Untested | **GAP** — URLs not validated | — |
| 10.2 | Deliberate no-AI choice → should frame as question | Untested | — | — |
| 10.3 | Regulated sub-niche → should soften gap language | Untested | **GAP** — no regulatory awareness | — |

**Aggregate:** 0 failures / 0 tests = **untested**

**Business cost:** CTO catches fabricated competitor claim → Tenacious credibility destroyed permanently. Highest-risk artifact in the system.
