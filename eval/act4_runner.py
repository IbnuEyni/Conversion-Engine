"""Act IV — Mechanism evaluation runner.

Runs baseline (llm_agent) vs mechanism (policy_aware_agent) on the
held-out τ²-Bench slice and produces:
  - ablation_results.json
  - held_out_traces.jsonl
  - Statistical test for Delta A

Usage:
    # Dev smoke test (2 tasks, 1 trial)
    uv run python eval/act4_runner.py --mode smoke

    # Dev run (5 tasks, 1 trial)
    uv run python eval/act4_runner.py --mode dev

    # Full held-out (20 tasks, 5 trials) — the real Act IV run
    uv run python eval/act4_runner.py --mode held_out

    # Ablation: run 3 variants on dev slice
    uv run python eval/act4_runner.py --mode ablation
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

load_dotenv(Path(__file__).parent.parent / ".env")

EVAL_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVAL_DIR.parent
TAU2_DIR = PROJECT_ROOT / "tau2-bench"
TAU2_BIN = TAU2_DIR / ".venv" / "bin" / "tau2"
TAU2_PYTHON = TAU2_DIR / ".venv" / "bin" / "python"
RESULTS_DIR = EVAL_DIR / "tau2_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

DEV_MODEL = os.getenv("DEV_MODEL", "qwen/qwen3-235b-a22b")

# Task splits
DEV_TASK_IDS = list(range(0, 5))
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


def register_and_run(
    agent_name: str,
    task_ids: list[int],
    num_trials: int,
    model: str,
    label: str,
    max_steps: int = 30,
    timeout: int = 300,
) -> dict:
    """Run a τ²-Bench evaluation with a specific agent."""
    model_full = f"openrouter/{model}" if "/" in model and "openrouter" not in model else model
    if "openrouter" not in model_full:
        model_full = f"openrouter/{model_full}"

    save_path = RESULTS_DIR / f"{label}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl"

    print(f"\n{'='*60}")
    print(f"Agent:  {agent_name}")
    print(f"Model:  {model_full}")
    print(f"Tasks:  {len(task_ids)} (IDs: {task_ids[0]}..{task_ids[-1]})")
    print(f"Trials: {num_trials}")
    print(f"Label:  {label}")
    print(f"{'='*60}\n")

    # For the policy_aware_agent, we need to register it before running
    if agent_name == "policy_aware_agent":
        # We run via a wrapper script that registers the agent
        cmd = [
            str(TAU2_PYTHON),
            str(EVAL_DIR / "_run_with_agent.py"),
            "--domain", "retail",
            "--agent", agent_name,
            "--agent-llm", model_full,
            "--user-llm", model_full,
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
            "--agent-llm", model_full,
            "--user-llm", model_full,
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
        for line in proc.stdout.strip().split("\n")[-20:]:
            print(line)
    if proc.returncode != 0 and proc.stderr:
        print(f"STDERR (last 500): {proc.stderr[-500:]}")

    results = parse_results(save_path)
    passed = sum(1 for r in results if r.get("reward", 0) > 0)
    total = len(results)
    pass_rate, ci_low, ci_high = wilson_ci95(passed, total)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "agent": agent_name,
        "model": model_full,
        "domain": "retail",
        "n_tasks": len(task_ids),
        "n_trials": num_trials,
        "total_simulations": total,
        "passed": passed,
        "pass_at_1": round(pass_rate, 4),
        "ci_95_low": round(ci_low, 4),
        "ci_95_high": round(ci_high, 4),
        "wall_clock_s": round(elapsed, 2),
        "results_file": str(save_path),
        "task_ids": task_ids,
    }

    print(f"\n{'='*60}")
    print(f"RESULT [{agent_name}]: {passed}/{total} = {pass_rate*100:.1f}% pass@1")
    print(f"95% CI: [{ci_low*100:.1f}%, {ci_high*100:.1f}%]")
    print(f"Wall clock: {elapsed:.1f}s")
    print(f"{'='*60}\n")

    return entry, results


def parse_results(results_path: Path) -> list[dict]:
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
            reward_info = sim.get("reward_info") or {}
            results.append({
                "task_id": sim.get("task_id", ""),
                "trial": sim.get("trial", 0),
                "reward": reward_info.get("reward", 0) if reward_info else 0,
                "n_messages": len(sim.get("messages", [])),
            })
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Warning: failed to parse {results_file}: {e}")
    return results


def fisher_exact_test(passed_a: int, total_a: int, passed_b: int, total_b: int) -> float:
    """One-sided Fisher's exact test: is B better than A?"""
    table = [
        [passed_b, total_b - passed_b],
        [passed_a, total_a - passed_a],
    ]
    _, p_value = stats.fisher_exact(table, alternative="greater")
    return p_value


def write_held_out_traces(traces: list[dict], label: str, agent: str, model: str):
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "label": label,
                "agent": agent,
                "model": model,
            }
            f.write(json.dumps(trace) + "\n")


def write_ablation_results(conditions: dict):
    """Write ablation_results.json."""
    path = EVAL_DIR / "ablation_results.json"
    path.write_text(json.dumps(conditions, indent=2))
    print(f"Wrote {path}")


def run_comparison(
    task_ids: list[int],
    num_trials: int,
    model: str = "",
    label_prefix: str = "act4",
    max_steps: int = 30,
    timeout: int = 300,
):
    """Run baseline vs mechanism and compute Delta A."""
    model = model or DEV_MODEL

    # Clear held_out_traces for fresh run
    traces_path = EVAL_DIR / "held_out_traces.jsonl"
    if traces_path.exists():
        traces_path.unlink()

    # 1. Baseline (standard llm_agent)
    baseline_entry, baseline_traces = register_and_run(
        agent_name="llm_agent",
        task_ids=task_ids,
        num_trials=num_trials,
        model=model,
        label=f"{label_prefix}_baseline",
        max_steps=max_steps,
        timeout=timeout,
    )
    write_held_out_traces(baseline_traces, f"{label_prefix}_baseline", "llm_agent", model)

    # 2. Mechanism (policy_aware_agent)
    mechanism_entry, mechanism_traces = register_and_run(
        agent_name="policy_aware_agent",
        task_ids=task_ids,
        num_trials=num_trials,
        model=model,
        label=f"{label_prefix}_mechanism",
        max_steps=max_steps,
        timeout=timeout,
    )
    write_held_out_traces(mechanism_traces, f"{label_prefix}_mechanism", "policy_aware_agent", model)

    # 3. Statistical test
    p_value = fisher_exact_test(
        baseline_entry["passed"], baseline_entry["total_simulations"],
        mechanism_entry["passed"], mechanism_entry["total_simulations"],
    )

    delta_a = mechanism_entry["pass_at_1"] - baseline_entry["pass_at_1"]

    print(f"\n{'='*60}")
    print(f"DELTA A (mechanism − baseline): {delta_a*100:+.1f}%")
    print(f"Baseline: {baseline_entry['pass_at_1']*100:.1f}% [{baseline_entry['ci_95_low']*100:.1f}%, {baseline_entry['ci_95_high']*100:.1f}%]")
    print(f"Mechanism: {mechanism_entry['pass_at_1']*100:.1f}% [{mechanism_entry['ci_95_low']*100:.1f}%, {mechanism_entry['ci_95_high']*100:.1f}%]")
    print(f"Fisher exact p-value: {p_value:.4f}")
    print(f"Significant at p<0.05: {'YES' if p_value < 0.05 else 'NO'}")
    print(f"{'='*60}\n")

    # 4. Write ablation_results.json
    ablation = {
        "comparison": {
            "task_ids": task_ids,
            "num_trials": num_trials,
            "model": f"openrouter/{model}",
            "domain": "retail",
        },
        "baseline": {
            "agent": "llm_agent",
            "pass_at_1": baseline_entry["pass_at_1"],
            "ci_95_low": baseline_entry["ci_95_low"],
            "ci_95_high": baseline_entry["ci_95_high"],
            "passed": baseline_entry["passed"],
            "total": baseline_entry["total_simulations"],
            "wall_clock_s": baseline_entry["wall_clock_s"],
        },
        "mechanism": {
            "agent": "policy_aware_agent",
            "pass_at_1": mechanism_entry["pass_at_1"],
            "ci_95_low": mechanism_entry["ci_95_low"],
            "ci_95_high": mechanism_entry["ci_95_high"],
            "passed": mechanism_entry["passed"],
            "total": mechanism_entry["total_simulations"],
            "wall_clock_s": mechanism_entry["wall_clock_s"],
        },
        "delta_a": {
            "value": round(delta_a, 4),
            "p_value": round(p_value, 6),
            "significant_at_005": bool(p_value < 0.05),
            "test": "fisher_exact_one_sided",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    write_ablation_results(ablation)

    return ablation


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Act IV mechanism evaluation")
    parser.add_argument("--mode", choices=["smoke", "dev", "held_out", "ablation"], default="smoke")
    parser.add_argument("--model", default="")
    parser.add_argument("--trials", type=int, default=0)
    args = parser.parse_args()

    if not TAU2_BIN.exists():
        print(f"ERROR: tau2-bench not found at {TAU2_DIR}")
        sys.exit(1)

    if args.mode == "smoke":
        run_comparison(
            task_ids=[0, 1],
            num_trials=1,
            model=args.model,
            label_prefix="smoke",
            max_steps=30,
            timeout=300,
        )
    elif args.mode == "dev":
        run_comparison(
            task_ids=DEV_TASK_IDS,
            num_trials=args.trials or 1,
            model=args.model,
            label_prefix="dev",
            max_steps=30,
            timeout=300,
        )
    elif args.mode == "held_out":
        run_comparison(
            task_ids=HELD_OUT_TASK_IDS,
            num_trials=args.trials or 5,
            model=args.model,
            label_prefix="held_out",
            max_steps=30,
            timeout=300,
        )
    elif args.mode == "ablation":
        # Run 3 ablation variants on dev slice
        model = args.model or DEV_MODEL
        trials = args.trials or 1

        traces_path = EVAL_DIR / "held_out_traces.jsonl"
        if traces_path.exists():
            traces_path.unlink()

        variants = {}

        # Variant 1: Baseline
        entry, traces = register_and_run("llm_agent", DEV_TASK_IDS, trials, model, "ablation_baseline")
        write_held_out_traces(traces, "ablation_baseline", "llm_agent", model)
        variants["baseline_llm_agent"] = entry

        # Variant 2: Policy-aware agent (full mechanism)
        entry, traces = register_and_run("policy_aware_agent", DEV_TASK_IDS, trials, model, "ablation_mechanism")
        write_held_out_traces(traces, "ablation_mechanism", "policy_aware_agent", model)
        variants["mechanism_policy_aware"] = entry

        # Variant 3: Baseline with higher max_steps (ablation: is it just step budget?)
        entry, traces = register_and_run("llm_agent", DEV_TASK_IDS, trials, model, "ablation_more_steps", max_steps=40)
        write_held_out_traces(traces, "ablation_more_steps", "llm_agent", model)
        variants["ablation_more_steps"] = entry

        ablation_path = EVAL_DIR / "ablation_results.json"
        ablation_path.write_text(json.dumps({"variants": variants, "timestamp": datetime.now(timezone.utc).isoformat()}, indent=2))
        print(f"\nAblation results written to {ablation_path}")
