# τ²-Bench Baseline — Act I Deliverable

## What Was Reproduced

τ²-Bench retail domain baseline using the dev-tier model (Qwen 235B-A22B) via OpenRouter. The retail domain simulates a customer service agent handling order cancellations, modifications, returns, and exchanges against a structured database with 50 product types and policy-constrained tool use.

## Results

| Metric | Value |
|---|---|
| Model | `openrouter/qwen/qwen3-235b-a22b` |
| Domain | retail |
| Tasks | 5 (dev slice, IDs 0–4) |
| Trials | 1 |
| pass@1 | **20.0%** (1/5) |
| 95% CI (Wilson) | [3.6%, 62.4%] |
| Published reference (GPT-5 class) | ~42% |
| Wall clock | 688s (11.5 min) |
| Cost per run | ~$0.003 (OpenRouter Qwen pricing) |

## Confidence Interval

Wide CI is expected at n=5. The full baseline run (30 tasks × 5 trials = 150 simulations) will narrow this significantly. At the current point estimate of 20%, a 150-simulation run would yield CI ≈ [14%, 28%].

## Observations

1. **Max-steps termination**: 3 of 5 tasks hit the 20-step limit. The model enters reasoning loops (Qwen's `<think>` blocks consume steps without tool calls). This is the primary failure mode to address in Act IV.

2. **Tool use accuracy**: When the model does call tools, read actions succeed at 37.5% and write actions at 50%. The bottleneck is not tool execution but deciding *which* tool to call and *when*.

3. **Authentication gap**: None of the 5 tasks checked user authentication, which the retail policy requires before any action. This is a systematic policy-adherence failure.

4. **Cost efficiency**: At ~$0.003 per 5-task run, the dev-tier model allows extensive iteration within the $4 budget for Days 1–4.

## Task Partitioning

- **Dev slice**: tasks 0–29 (30 tasks) — used for development and ablation
- **Held-out slice**: tasks 30–49 (20 tasks) — sealed for Act IV scoring
- **Test split**: 40 tasks — untouched (τ²-Bench official test set)

## Next Steps

- Full 30-task × 5-trial baseline run for tighter CI
- Investigate max-steps failures — likely addressable via prompt engineering or step-budget awareness
- Act IV mechanism targeting the authentication/policy-adherence gap
