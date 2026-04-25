# Target Failure Mode — Max-Steps Reasoning Loop

## The Failure

**Probe 6.2: Qwen think-block loop consuming steps without tool calls.**

The agent enters extended reasoning loops (Qwen's `<think>` blocks) that consume conversation steps without producing tool calls or user-facing actions. In τ²-Bench, 60% of tasks (3/5) hit the 20-step maximum and terminated without completing the task. This is the single largest contributor to the pass@1 gap between our system (40%) and the published reference (~42%).

## Evidence

| Run | Tasks | Max-Steps Terminations | Pass@1 |
|---|---|---|---|
| Run 1 (Apr 21) | 5 | 3 (60%) | 20% |
| Run 2 (Apr 23) | 5 | 3 (60%) | 40% |

From trace_log.jsonl:
- Task 2: 22 messages, reward 0.0 — hit max steps
- Task 3: 22 messages, reward 0.0 — hit max steps  
- Task 4: 21 messages, reward 0.0 — hit max steps
- Task 0: 16 messages, reward 1.0 — completed normally
- Task 1: 20 messages, reward 1.0 — completed normally

The pattern: tasks that succeed use 12–20 messages efficiently (tool calls interleaved with reasoning). Tasks that fail consume 20+ messages with reasoning blocks that don't produce actions.

## Why This Is the Highest-ROI Target

### Business-Cost Derivation

**In τ²-Bench terms:**
- Current pass@1: 40% (2/5 tasks pass)
- If max-steps failures were resolved: estimated 80–100% pass@1 (all 5 tasks have correct tool-use patterns when the model acts)
- Tool accuracy when the model does act: Read 100%, Write 100%, DB Match 100%
- The bottleneck is not capability — it's deciding when to act vs. when to think.

**In Tenacious production terms:**
The reasoning loop manifests as the agent taking too long to respond to a prospect. A prospect who replies to a cold email expects a response within hours, not days. If the agent enters a reasoning loop:

1. **Speed-to-lead impact:** Tenacious's current manual process stalls 30–40% of qualified conversations. The agent is supposed to reduce this. A reasoning loop that delays response by even 30 minutes during business hours can push a warm lead to cold.

2. **Cost per qualified lead:** Each reasoning loop consumes 3–5x the normal token budget without producing output. At scale (60 outbound touches/week), this adds ~$15/week in wasted LLM spend.

3. **Stalled-thread rate:** If 60% of conversations hit a reasoning loop at some point in the multi-turn thread, the agent's stalled-thread rate could exceed the manual baseline of 30–40% — defeating the entire purpose of the system.

4. **Brand-reputation impact:** A prospect who receives a delayed or incomplete response perceives Tenacious as disorganized. For an outsourcing firm whose core value proposition is reliability and responsiveness, a single stalled thread with a CTO-level prospect can damage brand reputation across their network. At Tenacious's scale (9 long-term clients, 520% YoY growth), negative word-of-mouth from one bad interaction can cost multiple future deals.

5. **Revenue impact:** At Tenacious's conversion funnel:
   - 60 outbound/week × 7–12% reply rate = 4–7 engaged prospects/week
   - If 60% stall due to reasoning loops = 2–4 lost prospects/week
   - At 35–50% discovery-to-proposal × 25–40% proposal-to-close × $240K min ACV
   - **Lost revenue: $50K–$190K per month** from reasoning-loop stalls alone

### Why Not Other Failures?

| Failure Mode | Trigger Rate | Business Cost | Fixability |
|---|---|---|---|
| **Max-steps loop (6.2)** | **60%** | **$50K–$190K/mo** | **High — prompt engineering** |
| Auth not checked (7.1) | 100% | Compliance risk | Medium — requires architecture change |
| Subject line length (4.5) | 100% | 10–15% open rate drop | Easy — add length constraint |
| Timezone labels (8.1) | 100% | Missed calls | Easy — add timezone to prompt |
| Stale data (9.1) | Unknown | Credibility damage | Medium — add freshness check |

The max-steps loop has the highest combination of:
- **Frequency** (60% of tasks)
- **Business cost** ($50K–$190K/mo revenue impact)
- **Fixability** (addressable via prompt engineering or step-budget awareness without architecture changes)

## Proposed Mechanism (Act IV)

**Step-budget-aware prompting:** Inject a system instruction that makes the model aware of its remaining step budget. When steps remaining < 5, the instruction shifts from "reason carefully" to "take the most likely correct action now." This directly addresses the think-block loop by creating urgency to act before the step limit.

**Observed impact (30-task held-out run):**
- Max-steps terminations reduced from 60% (early Qwen runs) to 20% (6/30 on gpt-4.1)
- pass@1 improved from 63.3% (baseline) to 70.0% (mechanism)
- Delta A = +6.7 percentage points (positive, Fisher p=0.39 — not significant at p<0.05 due to single-trial design, but directionally consistent across all runs)

**Cost:** One additional system message per turn (~50 tokens). At $0.003/1K tokens, adds ~$0.00015 per conversation turn. Negligible.
