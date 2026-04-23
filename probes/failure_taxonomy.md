# Failure Taxonomy — Probes Grouped by Category

## Summary

| Category | Probes | Active Failures | Highest Trigger Rate |
|---|---|---|---|
| 1. ICP Misclassification | 5 | 0 | 0% (all correct) |
| 2. Signal Over-Claiming | 4 | 0 | 0% (honesty flags working) |
| 3. Bench Over-Commitment | 3 | 0 | 0% (bench gating works) |
| 4. Tone Drift | 5 | 1 | 100% (subject line length) |
| 5. Multi-Thread Leakage | 2 | 0 | Untested |
| 6. Cost Pathology | 3 | 1 | 60% (max-steps in τ²-Bench) |
| 7. Dual-Control Coordination | 2 | 1 | 100% (auth never checked) |
| 8. Scheduling Edge Cases | 3 | 1 | 100% (timezone labels missing) |
| 9. Signal Reliability | 3 | 1 | Likely common (stale data) |
| 10. Gap Over-Claiming | 3 | 1 | Untested (URL validation gap) |
| **Total** | **33** | **5 confirmed** | |

---

## Category 1: ICP Misclassification (Probes 1.1–1.5)

**What it is:** Agent assigns prospect to wrong ICP segment, triggering wrong pitch language.

**Observed status:** All classification rules working correctly. Priority ordering (layoff overrides funding, leadership wins, AI maturity gates Segment 4) implemented and tested.

**Residual risk:** Edge cases with conflicting signals at boundary conditions (e.g., layoff at exactly 120 days, funding at exactly 180 days). Not yet fuzz-tested.

**Business cost range:** $240K–$720K per misclassified deal (one wrong pitch burns the contact).

---

## Category 2: Signal Over-Claiming (Probes 2.1–2.4)

**What it is:** Agent asserts facts about the prospect that are not supported by the enrichment data.

**Observed status:** Honesty flags (`weak_hiring_velocity_signal`, `weak_ai_maturity_signal`, `tech_stack_inferred_not_confirmed`) correctly propagated from pipeline to email composer. Confidence-aware phrasing working in demo.

**Residual risk:** LLM may ignore honesty flags in edge cases where the prompt is long and flags are buried.

**Business cost range:** Brand reputation damage. One viral screenshot of a wrong claim costs more than 100 correct outreach emails generate.

---

## Category 3: Bench Over-Commitment (Probes 3.1–3.3)

**What it is:** Agent promises engineering capacity the bench does not have.

**Observed status:** `bench_to_brief_match` correctly computed. Conversation manager loads fresh bench data on each reply. Gaps correctly identified.

**Residual risk:** Bench summary is a static JSON file updated weekly. Real-time staffing changes between updates could cause stale commitments.

**Business cost range:** Delivery failure on first engagement → client lost permanently + negative reference. $240K+ ACV at risk.

---

## Category 4: Tone Drift (Probes 4.1–4.5)

**What it is:** Agent's language deviates from the 5 Tenacious tone markers (Direct, Grounded, Honest, Professional, Non-condescending).

**Active failure:** Subject line length exceeds 60-character Gmail mobile limit (Probe 4.5). Demo generated 78-character subject.

**Residual risk:** Multi-turn conversations may gradually drift toward marketing language as the LLM loses context of the style guide constraints.

**Business cost range:** Low per-instance (open rate reduction) to catastrophic (viral LinkedIn roast of a bad email).

---

## Category 5: Multi-Thread Leakage (Probes 5.1–5.2)

**What it is:** Information from one prospect's conversation thread appears in another prospect's thread at the same company.

**Observed status:** Architecture is correct — threads keyed by prospect_id, not company domain. Not yet tested with concurrent multi-prospect scenarios.

**Business cost range:** High — internal politics disruption at prospect company, both contacts lost.

---

## Category 6: Cost Pathology (Probes 6.1–6.3)

**What it is:** Prompt patterns that cause excessive token usage or step consumption.

**Active failure:** τ²-Bench max-steps termination (Probe 6.2). 60% of tasks hit the 20-step limit due to Qwen's `<think>` blocks consuming steps without tool calls. **This is the primary τ²-Bench failure mode.**

**Residual risk:** In production, reasoning loops would manifest as slow response times (prospect waits minutes for a reply).

**Business cost range:** Direct: $0.03/prospect at 10x token blowup. Indirect: stalled threads from slow responses → 30–40% stall rate persists.

---

## Category 7: Dual-Control Coordination (Probes 7.1–7.2)

**What it is:** Agent fails to coordinate with the user (authenticate, confirm actions) before proceeding.

**Active failure:** Authentication never checked in τ²-Bench (Probe 7.1). 100% trigger rate across all 5 tasks in both runs.

**Residual risk:** In Tenacious context, this manifests as the agent taking actions (booking calls, sending emails) without proper prospect confirmation.

**Business cost range:** Compliance risk + wasted delivery lead time on unconfirmed bookings.

---

## Category 8: Scheduling Edge Cases (Probes 8.1–8.3)

**What it is:** Time zone confusion, weekend bookings, or overlap-window miscommunication.

**Active failure:** Demo reply proposed meeting times without explicit timezone labels (Probe 8.1).

**Residual risk:** Tenacious serves US, EU, and East Africa — three timezone regions. Confusion is likely with real prospects.

**Business cost range:** Missed discovery calls → stalled threads. Each missed call delays pipeline by 1–2 weeks.

---

## Category 9: Signal Reliability (Probes 9.1–9.3)

**What it is:** Enrichment data is stale, incomplete, or falsely matched.

**Active failure:** No data freshness check on Crunchbase records (Probe 9.1). Fuzzy company name matching could produce false layoff positives (Probe 9.3).

**Residual risk:** The Crunchbase ODM sample is a frozen snapshot. Companies that changed status after the snapshot will have stale data.

**Business cost range:** Factual errors in first email → credibility destruction. One wrong "you recently raised" or "you recently laid off" is unrecoverable.

---

## Category 10: Gap Over-Claiming (Probes 10.1–10.3)

**What it is:** Competitor gap brief contains unverifiable claims or frames a deliberate strategic choice as a deficiency.

**Active failure:** Source URLs in gap findings are LLM-generated and not validated (Probe 10.1). No regulatory-context awareness (Probe 10.3).

**Residual risk:** The competitor gap brief is the highest-value and highest-risk artifact. A wrong gap finding delivered to a CTO is worse than no gap finding at all.

**Business cost range:** Brand reputation damage. A CTO who catches a fabricated competitor claim will never engage with Tenacious again and may warn their network.
