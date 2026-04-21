"""τ²-Bench evaluation harness for the Conversion Engine.

Wraps Sierra Research's tau2-bench to:
1. Run retail domain baseline with pinned model via OpenRouter
2. Collect pass@1 results with 95% Wilson CI
3. Write score_log.json and trace_log.jsonl
4. Support dev slice / held-out slice partitioning

Usage:
    # Quick smoke test (1 task, 1 trial)
    uv run python eval/harness.py --mode smoke

    # Dev baseline (5 tasks, 1 trial — fast iteration)
    uv run python eval/harness.py --mode dev

    # Full baseline (30 dev tasks, 5 trials — Act I deliverable)
    uv run python eval/harness.py --mode baseline

    # Held-out scoring (20 tasks, sealed — Act IV)
    uv run python eval/harness.py --mode held_out
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

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

EVAL_DIR = Path(__file__).parent
PROJECT_ROOT = EVAL_DIR.parent
TAU2_DIR = PROJECT_ROOT / "tau2-bench"
TAU2_BIN = TAU2_DIR / ".venv" / "bin" / "tau2"
TAU2_PYTHON = TAU2_DIR / ".venv" / "bin" / "python"
SCORE_LOG = EVAL_DIR / "score_log.json"
RESULTS_DIR = EVAL_DIR / "tau2_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Pinned model config (challenge doc: dev tier)
DEV_MODEL = os.getenv("DEV_MODEL", "qwen/qwen3-235b-a22b")
DEV_TEMPERATURE = float(os.getenv("DEV_TEMPERATURE", "0.3"))
EVAL_MODEL = os.getenv("EVAL_MODEL", "anthropic/claude-sonnet-4")

# Task splits: 74 train tasks, we use first 30 as dev, next 20 as held-out
# Remaining 24 are buffer. Test split (40 tasks) is untouched.
DEV_TASK_IDS = list(range(0, 30))
HELD_OUT_TASK_IDS = list(range(30, 50))


def compute_wilson_ci95(successes: int, n: int) -> tuple[float, float, float]:
    """Wilson score interval for 95% CI on a proportion."""
    if n == 0:
        return 0.0, 0.0, 0.0
    p = successes / n
    z = 1.96
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    spread = z * math.sqrt((p * (1 - p) + z ** 2 / (4 * n)) / n) / denom
    return p, max(0, center - spread), min(1, center + spread)


def run_tau2(
    task_ids: list[int],
    num_trials: int = 1,
    model: str = "",
    label: str = "baseline",
    max_steps: int = 20,
    timeout: int = 180,
    max_concurrency: int = 1,
) -> dict:
    """Run tau2-bench retail domain and collect results."""
    model = model or f"openrouter/{DEV_MODEL}"
    save_path = RESULTS_DIR / f"{label}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl"

    print(f"\n{'=' * 60}")
    print(f"τ²-Bench Retail Baseline")
    print(f"Model:  {model}")
    print(f"Tasks:  {len(task_ids)} (IDs: {task_ids[0]}..{task_ids[-1]})")
    print(f"Trials: {num_trials}")
    print(f"Label:  {label}")
    print(f"{'=' * 60}\n")

    # Build command
    cmd = [
        str(TAU2_BIN),
        "run",
        "--domain", "retail",
        "--agent", "llm_agent",
        "--agent-llm", model,
        "--user-llm", model,
        "--num-trials", str(num_trials),
        "--max-steps", str(max_steps),
        "--timeout", str(timeout),
        "--max-concurrency", str(max_concurrency),
        "--save-to", str(save_path),
        "--seed", "42",
        "--log-level", "WARNING",
        "--task-ids",
    ] + [str(tid) for tid in task_ids]

    env = {
        **os.environ,
        "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
    }

    start = time.time()
    print(f"Running: {' '.join(cmd[:8])}... ({len(task_ids)} tasks)")

    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=str(TAU2_DIR))
    elapsed = time.time() - start

    if proc.stdout:
        # Print the summary table from tau2
        lines = proc.stdout.strip().split("\n")
        for line in lines[-30:]:
            print(line)

    if proc.returncode != 0 and proc.stderr:
        print(f"STDERR (last 500): {proc.stderr[-500:]}")

    # Parse results from saved JSONL
    results = parse_results(save_path)
    passed = sum(1 for r in results if r.get("reward", 0) > 0)
    total = len(results)

    pass_rate, ci_low, ci_high = compute_wilson_ci95(passed, total)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "model": model,
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

    # Write score log
    existing = []
    if SCORE_LOG.exists():
        try:
            existing = json.loads(SCORE_LOG.read_text())
        except json.JSONDecodeError:
            existing = []
    existing.append(entry)
    SCORE_LOG.write_text(json.dumps(existing, indent=2))

    # Write trace log entries
    trace_log = EVAL_DIR / "trace_log.jsonl"
    with open(trace_log, "a") as f:
        for r in results:
            trace = {
                "trace_id": f"tau2_{label}_{r.get('task_id', 'unknown')}_{r.get('trial', 0)}",
                "type": "tau2_eval",
                "task_id": r.get("task_id"),
                "trial": r.get("trial"),
                "reward": r.get("reward", 0),
                "passed": r.get("reward", 0) > 0,
                "n_messages": r.get("n_messages", 0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "label": label,
                "model": model,
            }
            f.write(json.dumps(trace) + "\n")

    print(f"\n{'=' * 60}")
    print(f"RESULT: {passed}/{total} = {pass_rate * 100:.1f}% pass@1")
    print(f"95% CI: [{ci_low * 100:.1f}%, {ci_high * 100:.1f}%]")
    print(f"Wall clock: {elapsed:.1f}s ({elapsed / 60:.1f}m)")
    print(f"Score log: {SCORE_LOG}")
    print(f"Results:   {save_path}")
    print(f"{'=' * 60}\n")

    return entry


def parse_results(results_path: Path) -> list[dict]:
    """Parse tau2-bench results. tau2 saves as a directory with results.json inside."""
    results = []

    # tau2 creates a directory with results.json
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
            reward_info = sim.get("reward_info", {})
            results.append({
                "task_id": sim.get("task_id", ""),
                "trial": sim.get("trial", 0),
                "reward": reward_info.get("reward", 0),
                "n_messages": len(sim.get("messages", [])),
            })
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Warning: failed to parse {results_file}: {e}")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="τ²-Bench evaluation harness")
    parser.add_argument("--mode", choices=["smoke", "dev", "baseline", "held_out"], default="smoke")
    parser.add_argument("--model", default="")
    parser.add_argument("--trials", type=int, default=0)
    parser.add_argument("--max-concurrency", type=int, default=1)
    args = parser.parse_args()

    if not TAU2_BIN.exists():
        print(f"ERROR: tau2-bench not found at {TAU2_DIR}")
        print("Run: cd tau2-bench && uv venv --python 3.12 .venv && uv pip install -e .")
        sys.exit(1)

    if args.mode == "smoke":
        run_tau2(task_ids=[0], num_trials=1, model=args.model, label="smoke_test",
                 max_concurrency=args.max_concurrency)

    elif args.mode == "dev":
        run_tau2(task_ids=DEV_TASK_IDS[:5], num_trials=args.trials or 1, model=args.model,
                 label="dev_quick", max_concurrency=args.max_concurrency)

    elif args.mode == "baseline":
        run_tau2(task_ids=DEV_TASK_IDS, num_trials=args.trials or 5, model=args.model,
                 label="dev_baseline", max_concurrency=args.max_concurrency)

    elif args.mode == "held_out":
        run_tau2(task_ids=HELD_OUT_TASK_IDS, num_trials=args.trials or 5, model=args.model,
                 label="held_out", max_concurrency=args.max_concurrency)
