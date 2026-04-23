# τ²-Bench Baseline — Act I Deliverable

## Official Instructor-Provided Baseline

The program staff provided the official τ²-Bench retail baseline to ensure all trainees work from the same reference point.

| Metric | Value |
|---|---|
| Model | `openrouter/qwen/qwen3-235b-a22b` |
| Domain | retail |
| Tasks | 30 |
| Trials per task | 5 |
| Total simulations | 150 |
| **pass@1** | **72.67%** |
| **95% CI** | **[65.04%, 79.17%]** |
| Avg agent cost/conversation | $0.0199 |
| p50 latency | 105.95s |
| p95 latency | 551.65s |
| Infra errors | 0 |
| Git commit | `d11a97072c49d093f7b5a3e4fe9da95b490d43ba` |

## Our Reproduction Runs (Dev Slice, Tasks 0–4)

Three independent runs on the 5-task dev subset, 1 trial each.

| Run | pass@1 | 95% CI | Wall Clock | Max-Steps Rate |
|---|---|---|---|---|
| Run 1 (Apr 21) | 20.0% (1/5) | [3.6%, 62.4%] | 688s | 60% |
| Run 2 (Apr 23) | 40.0% (2/5) | [11.8%, 76.9%] | 707s | 60% |
| Run 3 (Apr 23) | 20.0% (1/5) | [3.6%, 62.4%] | 710s | 80% |
| **Pooled** | **26.7% (4/15)** | **[10.9%, 52.0%]** | | **67%** |

## Confidence Interval

Our pooled CI [10.9%, 52.0%] is wide due to small sample size (n=15). The official baseline CI [65.04%, 79.17%] is tight at n=150. Our dev-slice runs underperform the official baseline — the gap is attributable to the high max-steps termination rate (67%) on our specific 5-task subset and the inherent variance at small n.

## Cost

- Our runs: ~$0.003 per 5-task run (OpenRouter Qwen pricing)
- Official baseline: $0.0199 avg per conversation × 150 = ~$2.99 total

## Observations

1. **Max-steps termination is the dominant failure mode.** 67% of our tasks hit the 20-step limit. The model enters reasoning loops (`<think>` blocks) that consume steps without tool calls. This is the primary target for Act IV.

2. **Tool accuracy is perfect when the model acts.** Read actions 100%, Write actions 100%, DB Match 100%. The bottleneck is deciding *when* to act, not *how* to act.

3. **Authentication never checked.** 0/15 tasks verified user identity before proceeding. Systematic policy-adherence failure across all runs.

4. **Variance is high at n=5.** The 20%–40% swing between runs is expected. The official 150-simulation baseline eliminates this variance.

## Next Steps (Act IV)

- Implement step-budget-aware prompting to reduce max-steps failures
- Run 1 trial on held-out slice per updated instructor guidance ($10 budget)
- Target: close the gap toward the 72.67% official baseline
