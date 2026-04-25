"""Act IV — Mechanism evaluation runner.

Runs baseline (llm_agent) vs mechanism (policy_aware_agent) on τ²-Bench
using gpt-4.1 via OpenRouter to match the instructor baseline.

Produces:
  - ablation_results.json
  - held_out_traces.jsonl
  - Statistical test for Delta A

Usage:
    # Dev run (5 tasks, 1 trial each condition)
    python3 eval/act4_runner.py --mode dev

    # Full held-out (20 tasks, 5 trials)
    python3 eval/act4_runner.py --mode held_out
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from scipy import stats

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

EVAL_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVAL_DIR.parent
TAU2_DIR = PROJECT_ROOT / "tau2-bench"
TAU2_BIN = TAU2_DIR / ".venv" / "bin" / "tau2"
TAU2_PYTHON = TAU2_DIR / ".venv" / "bin" / "python"
RESULTS_DIR = EVAL_DIR / "tau2_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Match instructor config: gpt-4.1 via OpenRouter
MODEL = "openrouter/openai/gpt-4.1"

DEV_TASK_IDS = list(range(0, 30))
HELD_OUT_TASK_IDS = list(range(30, 50))


def wilson_ci95(successes: int, n: int) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    p = successes / n
    z = 1.96
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    spread = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
    return p, max(0, center - spread), min(1, center + spread)


def parse_results(results_path: Path) -> list[dict]:
    """Parse tau2-bench results and extract per-task cost/token info."""
    results = []
    if results_path.is_dir():
        results_file = results_path / "results.json"
    elif results_path.is_file():
        results_file = results_path
    else:
        return results

    if not results_file.exists():
        return results

    try:
        data = json.loads(results_file.read_text())
        for sim in data.get("simulations", []):
            ri = sim.get("reward_info") or {}
            reward = ri.get("reward", 0) if ri else 0
            messages = sim.get("messages", [])

            # Extract token usage and cost from messages
            agent_tokens = 0
            user_tokens = 0
            agent_cost = 0.0
            user_cost = 0.0
            for msg in messages:
                usage = msg.get("usage") or {}
                cost = msg.get("cost") or 0.0
                prompt_t = usage.get("prompt_tokens", 0)
                completion_t = usage.get("completion_tokens", 0)
                role = msg.get("role", "")
                if role == "assistant":
                    agent_tokens += prompt_t + completion_t
                    agent_cost += cost
                elif role == "user":
                    user_tokens += prompt_t + completion_t
                    user_cost += cost

            results.append({
                "task_id": sim.get("task_id", ""),
                "trial": sim.get("trial", 0),
                "reward": reward,
                "n_messages": len(messages),
                "agent_tokens": agent_tokens,
                "user_tokens": user_tokens,
                "agent_cost": round(agent_cost, 6),
                "user_cost": round(user_cost, 6),
                "total_cost": round(agent_cost + user_cost, 6),
            })
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Warning: failed to parse {results_file}: {e}")
    return results


def run_agent(
    agent_name: str,
    task_ids: list[int],
    num_trials: int,
    label: str,
    max_steps: int = 30,
    timeout: int = 300,
) -> tuple[dict, list[dict]]:
    """Run a τ²-Bench evaluation with a specific agent."""
    save_path = RESULTS_DIR / f"{label}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl"

    print(f"\n{'='*60}")
    print(f"Agent:  {agent_name}")
    print(f"Model:  {MODEL}")
    print(f"Tasks:  {len(task_ids)} (IDs: {task_ids[0]}..{task_ids[-1]})")
    print(f"Trials: {num_trials}")
    print(f"Label:  {label}")
    print(f"{'='*60}\n")

    if agent_name == "policy_aware_agent":
        cmd = [
            str(TAU2_PYTHON),
            str(EVAL_DIR / "_run_with_agent.py"),
            "--domain", "retail",
            "--agent", agent_name,
            "--agent-llm", MODEL,
            "--user-llm", MODEL,
            "--num-trials", str(num_trials),
            "--max-steps", str(max_steps),
            "--timeout", str(timeout),
            "--max-concurrency", "1",
            "--save-to", str(save_path),
            "--seed", "42",
            "--log-level", "WARNING",
            "--task-ids",
        ] + [str(tid) for tid in task_ids]
    else:
        cmd = [
            str(TAU2_BIN),
            "run",
            "--domain", "retail",
            "--agent", agent_name,
            "--agent-llm", MODEL,
            "--user-llm", MODEL,
            "--num-trials", str(num_trials),
            "--max-steps", str(max_steps),
            "--timeout", str(timeout),
            "--max-concurrency", "1",
            "--save-to", str(save_path),
            "--seed", "42",
            "--log-level", "WARNING",
            "--task-ids",
        ] + [str(tid) for tid in task_ids]

    env = {**os.environ, "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", "")}

    start = time.time()
    print(f"Running: {agent_name} on {len(task_ids)} tasks...")
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=str(TAU2_DIR))
    elapsed = time.time() - start

    if proc.stdout:
        for line in proc.stdout.strip().split("\n")[-25:]:
            print(line)
    if proc.returncode != 0 and proc.stderr:
        stderr_lines = proc.stderr.strip().split("\n")
        # Only show real errors, not litellm warnings
        errors = [l for l in stderr_lines if "ERROR" in l and "model isn't mapped" not in l]
        if errors:
            print(f"ERRORS: {errors[-3:]}")

    results = parse_results(save_path)
    passed = sum(1 for r in results if r.get("reward", 0) > 0)
    total = len(results)
    pass_rate, ci_low, ci_high = wilson_ci95(passed, total)

    total_cost = sum(r.get("total_cost", 0) for r in results)
    total_tokens = sum(r.get("agent_tokens", 0) + r.get("user_tokens", 0) for r in results)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "agent": agent_name,
        "model": MODEL,
        "domain": "retail",
        "n_tasks": len(task_ids),
        "n_trials": num_trials,
        "total_simulations": total,
        "passed": passed,
        "pass_at_1": round(pass_rate, 4),
        "ci_95_low": round(ci_low, 4),
        "ci_95_high": round(ci_high, 4),
        "wall_clock_s": round(elapsed, 2),
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "cost_per_task": round(total_cost / max(total, 1), 6),
        "results_file": str(save_path),
        "task_ids": task_ids,
    }

    print(f"\n{'='*60}")
    print(f"RESULT [{agent_name}]: {passed}/{total} = {pass_rate*100:.1f}% pass@1")
    print(f"95% CI: [{ci_low*100:.1f}%, {ci_high*100:.1f}%]")
    print(f"Cost: ${total_cost:.4f} total, ${entry['cost_per_task']:.4f}/task")
    print(f"Tokens: {total_tokens:,} total")
    print(f"Wall clock: {elapsed:.1f}s ({elapsed/60:.1f}m)")
    print(f"{'='*60}\n")

    # Print per-task breakdown
    print("Per-task breakdown:")
    print(f"{'Task':>6} {'Reward':>8} {'Msgs':>6} {'AgentTok':>10} {'UserTok':>10} {'Cost':>10}")
    for r in results:
        print(f"{r['task_id']:>6} {r['reward']:>8.1f} {r['n_messages']:>6} {r['agent_tokens']:>10,} {r['user_tokens']:>10,} ${r['total_cost']:>9.4f}")
    print()

    return entry, results


def run_comparison(
    task_ids: list[int],
    num_trials: int,
    label_prefix: str = "act4",
    max_steps: int = 30,
    timeout: int = 300,
):
    """Run baseline vs mechanism and compute Delta A."""

    # Clear held_out_traces for fresh run
    traces_path = EVAL_DIR / "held_out_traces.jsonl"
    if traces_path.exists():
        traces_path.unlink()

    # 1. Baseline
    baseline_entry, baseline_traces = run_agent(
        agent_name="llm_agent",
        task_ids=task_ids,
        num_trials=num_trials,
        label=f"{label_prefix}_baseline",
        max_steps=max_steps,
        timeout=timeout,
    )
    write_traces(baseline_traces, f"{label_prefix}_baseline", "llm_agent")

    # 2. Mechanism
    mechanism_entry, mechanism_traces = run_agent(
        agent_name="policy_aware_agent",
        task_ids=task_ids,
        num_trials=num_trials,
        label=f"{label_prefix}_mechanism",
        max_steps=max_steps,
        timeout=timeout,
    )
    write_traces(mechanism_traces, f"{label_prefix}_mechanism", "policy_aware_agent")

    # 3. Statistical test
    table = [
        [mechanism_entry["passed"], mechanism_entry["total_simulations"] - mechanism_entry["passed"]],
        [baseline_entry["passed"], baseline_entry["total_simulations"] - baseline_entry["passed"]],
    ]
    _, p_value = stats.fisher_exact(table, alternative="greater")
    delta_a = mechanism_entry["pass_at_1"] - baseline_entry["pass_at_1"]

    print(f"\n{'='*60}")
    print(f"DELTA A (mechanism − baseline): {delta_a*100:+.1f}%")
    print(f"Baseline:  {baseline_entry['pass_at_1']*100:.1f}% [{baseline_entry['ci_95_low']*100:.1f}%, {baseline_entry['ci_95_high']*100:.1f}%]")
    print(f"Mechanism: {mechanism_entry['pass_at_1']*100:.1f}% [{mechanism_entry['ci_95_low']*100:.1f}%, {mechanism_entry['ci_95_high']*100:.1f}%]")
    print(f"Fisher exact p-value: {p_value:.4f}")
    print(f"Significant at p<0.05: {'YES' if p_value < 0.05 else 'NO'}")
    print(f"")
    print(f"Cost summary:")
    print(f"  Baseline:  ${baseline_entry['total_cost_usd']:.4f} ({baseline_entry['total_tokens']:,} tokens)")
    print(f"  Mechanism: ${mechanism_entry['total_cost_usd']:.4f} ({mechanism_entry['total_tokens']:,} tokens)")
    print(f"{'='*60}\n")

    # 4. Write ablation_results.json
    ablation = {
        "comparison": {
            "task_ids": task_ids,
            "num_trials": num_trials,
            "model": MODEL,
            "domain": "retail",
            "instructor_baseline_reference": {
                "pass_at_1": 0.7267,
                "ci_95": [0.6504, 0.7917],
                "n_tasks": 30,
                "n_trials": 5,
                "total_simulations": 150,
                "model": "gpt-4.1-2025-04-14",
            },
        },
        "baseline": {
            "agent": "llm_agent",
            "description": "Default tau2-bench LLM agent with standard system prompt, gpt-4.1 via OpenRouter",
            "pass_at_1": baseline_entry["pass_at_1"],
            "ci_95_low": baseline_entry["ci_95_low"],
            "ci_95_high": baseline_entry["ci_95_high"],
            "passed": baseline_entry["passed"],
            "total": baseline_entry["total_simulations"],
            "wall_clock_s": baseline_entry["wall_clock_s"],
            "total_cost_usd": baseline_entry["total_cost_usd"],
            "total_tokens": baseline_entry["total_tokens"],
            "cost_per_task": baseline_entry["cost_per_task"],
        },
        "mechanism": {
            "agent": "policy_aware_agent",
            "description": "Enhanced system prompt with auth-first workflow and action discipline, gpt-4.1 via OpenRouter",
            "pass_at_1": mechanism_entry["pass_at_1"],
            "ci_95_low": mechanism_entry["ci_95_low"],
            "ci_95_high": mechanism_entry["ci_95_high"],
            "passed": mechanism_entry["passed"],
            "total": mechanism_entry["total_simulations"],
            "wall_clock_s": mechanism_entry["wall_clock_s"],
            "total_cost_usd": mechanism_entry["total_cost_usd"],
            "total_tokens": mechanism_entry["total_tokens"],
            "cost_per_task": mechanism_entry["cost_per_task"],
        },
        "delta_a": {
            "value": round(delta_a, 4),
            "description": "mechanism pass@1 - baseline pass@1",
            "positive": bool(delta_a > 0),
            "p_value": round(float(p_value), 6),
            "significant_at_005": bool(p_value < 0.05),
            "test": "fisher_exact_one_sided",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    ablation_path = EVAL_DIR / "ablation_results.json"
    ablation_path.write_text(json.dumps(ablation, indent=2))
    print(f"Wrote {ablation_path}")

    return ablation


def write_traces(traces: list[dict], label: str, agent: str):
    """Append traces to held_out_traces.jsonl."""
    path = EVAL_DIR / "held_out_traces.jsonl"
    with open(path, "a") as f:
        for r in traces:
            trace = {
                "trace_id": f"act4_{label}_{r.get('task_id', 'unknown')}_{r.get('trial', 0)}",
                "type": "tau2_eval",
                "task_id": r.get("task_id"),
                "trial": r.get("trial"),
                "reward": r.get("reward", 0),
                "passed": r.get("reward", 0) > 0,
                "n_messages": r.get("n_messages", 0),
                "agent_tokens": r.get("agent_tokens", 0),
                "user_tokens": r.get("user_tokens", 0),
                "agent_cost": r.get("agent_cost", 0),
                "user_cost": r.get("user_cost", 0),
                "total_cost": r.get("total_cost", 0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "label": label,
                "agent": agent,
                "model": MODEL,
            }
            f.write(json.dumps(trace) + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Act IV mechanism evaluation")
    parser.add_argument("--mode", choices=["dev", "held_out"], default="dev")
    parser.add_argument("--trials", type=int, default=0)
    args = parser.parse_args()

    if not TAU2_BIN.exists():
        print(f"ERROR: tau2-bench not found at {TAU2_DIR}")
        sys.exit(1)

    if args.mode == "dev":
        run_comparison(
            task_ids=DEV_TASK_IDS,
            num_trials=args.trials or 1,
            label_prefix="dev_gpt41",
            max_steps=30,
            timeout=300,
        )
    elif args.mode == "held_out":
        run_comparison(
            task_ids=HELD_OUT_TASK_IDS,
            num_trials=args.trials or 5,
            label_prefix="held_out_gpt41",
            max_steps=30,
            timeout=300,
        )
