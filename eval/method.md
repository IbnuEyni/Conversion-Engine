# Method — Policy-Aware Agent (Act IV Mechanism)

## Target Failure Mode

**Max-steps reasoning loop + authentication skipping** (Probes 6.2 and 7.1).

From Act III analysis:
- 60% of τ²-Bench tasks hit the 20-step limit due to Qwen's `<think>` blocks consuming steps without producing tool calls
- 100% of tasks failed to check user authentication before taking actions
- Combined, these two failures account for the entire gap between our baseline (20–40% pass@1) and the published reference (~42%)

## Mechanism Design

**Policy-Aware Prompting** — a modified system prompt that addresses both failure modes simultaneously through explicit behavioral instructions rather than architectural changes.

### Key changes from the default `llm_agent`:

1. **Authentication-first workflow**: The prompt explicitly defines a 5-step workflow starting with identity verification. The default τ²-Bench `llm_agent` says "follow the policy" but does not front-load authentication as a mandatory first step.

2. **Action discipline**: Each turn must produce a visible output (tool call OR message). The prompt explicitly prohibits spending turns on internal reasoning only. This directly counters the `<think>` block loop where Qwen reasons for multiple turns without acting.

3. **Confirm-before-write**: Write operations require explicit user confirmation. This addresses the dual-control coordination failure (Probe 7.2).

4. **One-action-per-turn enforcement**: Reinforced in the prompt to prevent the model from attempting multiple tool calls in a single turn (which τ²-Bench penalizes).

### Why prompt-level, not architecture-level?

- **Cost**: Zero additional LLM calls. The mechanism adds ~200 tokens to the system prompt (~$0.00004 per conversation at Qwen pricing). Compare to ReAct (2x calls per turn) or tone-check (1 additional call per turn).
- **Compatibility**: Works with any model via OpenRouter. No model-specific features required.
- **Simplicity**: Single point of change. Easy to audit, easy to revert.

## Hyperparameters

| Parameter | Value | Rationale |
|---|---|---|
| System prompt length | ~350 tokens | Fits within Qwen's context window with room for policy + conversation |
| max_steps | 30 | Increased from 20 to give the model more room while the prompt reduces wasted steps |
| temperature | 0.3 | Same as baseline (dev tier setting) |
| timeout | 300s | 5 min per task, generous for retail domain |

## Ablation Variants

Three variants tested on the dev slice (tasks 0–4):

1. **Baseline** (`llm_agent`, max_steps=30): Standard τ²-Bench agent with default prompt. Isolates whether the improvement comes from the prompt or the step budget.

2. **Mechanism** (`policy_aware_agent`, max_steps=30): Full mechanism with enhanced prompt. The treatment condition.

3. **More steps only** (`llm_agent`, max_steps=40): Baseline agent with even more steps. Tests whether simply giving the model more room to reason is sufficient, or whether the prompt discipline is necessary.

If variant 3 matches variant 2, the mechanism is just a step-budget effect. If variant 2 outperforms variant 3, the prompt discipline is the active ingredient.

## Statistical Test

**Fisher's exact test (one-sided)**: Tests whether the mechanism's pass rate is significantly higher than the baseline's.

- H₀: mechanism pass rate ≤ baseline pass rate
- H₁: mechanism pass rate > baseline pass rate
- Significance level: α = 0.05

Delta A = mechanism pass@1 − baseline pass@1. Must be positive with p < 0.05.

## Expected Impact

Based on failure mode analysis:
- Fixing auth skipping alone should recover tasks that fail on policy adherence
- Fixing reasoning loops should recover tasks that hit max-steps
- Combined: estimated 20–40 percentage point improvement in pass@1

## Cost Analysis

| Component | Baseline | Mechanism | Delta |
|---|---|---|---|
| System prompt tokens | ~150 | ~350 | +200 tokens (~$0.00004) |
| LLM calls per task | Same | Same | 0 |
| Wall clock per task | ~140s | ~140s (expected) | ~0 |
| Total cost per eval run | ~$0.003 | ~$0.003 | Negligible |
