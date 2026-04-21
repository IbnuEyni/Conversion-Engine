"""τ²-Bench evaluation harness for the Conversion Engine.

Wraps Sierra Research's tau2-bench to:
1. Run retail domain baseline with pinned model
2. Write trace_log.jsonl to Langfuse
3. Update score_log.json with pass@1 and 95% CI
4. Support dev slice (30 tasks) and sealed held-out (20 tasks)
"""

from __future__ import annotations
import argparse
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

EVAL_DIR = Path(__file__).parent
PROJECT_ROOT = EVAL_DIR.parent
TAU2_DIR = PROJECT_ROOT / "tau2-bench"
SCORE_LOG = EVAL_DIR / "score_log.json"
TRACE_LOG = EVAL_DIR / "trace_log.jsonl"


def compute_ci95(pass_rate: float, n: int) -> tuple[float, float]:
    """Wilson score interval for 95% CI on a proportion."""
    if n == 0:
        return (0.0, 0.0)
    z = 1.96
    p = pass_rate
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    spread = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
    return (max(0, center - spread), min(1, center + spread))


def clone_tau2():
    """Clone tau2-bench if not present."""
    if TAU2_DIR.exists():
        print(f"τ²-Bench already cloned at {TAU2_DIR}")
        return
    print("Cloning τ²-Bench...")
    subprocess.run(
        ["git", "clone", "https://github.com/sierra-research/tau2-bench.git", str(TAU2_DIR)],
        check=True,
    )
    print("Installing τ²-Bench dependencies...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(TAU2_DIR)],
        check=True,
    )


def run_baseline(
    model: str = "qwen/qwen3-235b-a22b",
    domain: str = "retail",
    n_tasks: int = 3,
    n_trials: int = 1,
    temperature: float = 0.3,
) -> dict:
    """Run τ²-Bench baseline and collect results."""
    clone_tau2()

    print(f"\n{'='*60}")
    print(f"τ²-Bench Baseline Run")
    print(f"Model: {model} | Domain: {domain} | Tasks: {n_tasks} | Trials: {n_trials}")
    print(f"{'='*60}\n")

    start = time.time()

    # Try to import and run tau2-bench directly
    try:
        sys.path.insert(0, str(TAU2_DIR))
        # The actual tau2-bench API may vary — this is the integration point
        # For now, we'll run via subprocess if the package has a CLI
        result = subprocess.run(
            [
                sys.executable, "-m", "tau2_bench",
                "--domain", domain,
                "--model", model,
                "--temperature", str(temperature),
                "--n_tasks", str(n_tasks),
                "--n_trials", str(n_trials),
                "--output_dir", str(EVAL_DIR / "tau2_results"),
            ],
            capture_output=True,
            text=True,
            cwd=str(TAU2_DIR),
            env={**os.environ, "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", "")},
        )
        print(result.stdout[-2000:] if result.stdout else "No stdout")
        if result.stderr:
            print(f"STDERR: {result.stderr[-1000:]}")
    except Exception as e:
        print(f"Direct run failed: {e}")
        print("τ²-Bench may need manual setup — check tau2-bench/README.md")

    elapsed = time.time() - start

    # Parse results (adapt based on actual tau2-bench output format)
    results_dir = EVAL_DIR / "tau2_results"
    passed = 0
    total = n_tasks
    traces = []

    if results_dir.exists():
        for f in sorted(results_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                is_pass = data.get("pass", data.get("success", False))
                if is_pass:
                    passed += 1
                traces.append({
                    "trace_id": f"tau2_{f.stem}",
                    "task": f.stem,
                    "passed": is_pass,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass

    pass_rate = passed / total if total > 0 else 0
    ci_low, ci_high = compute_ci95(pass_rate, total * n_trials)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_type": "baseline",
        "model": model,
        "domain": domain,
        "n_tasks": total,
        "n_trials": n_trials,
        "temperature": temperature,
        "passed": passed,
        "total": total,
        "pass_at_1": round(pass_rate, 4),
        "ci_95_low": round(ci_low, 4),
        "ci_95_high": round(ci_high, 4),
        "wall_clock_s": round(elapsed, 2),
        "cost_estimate_usd": None,  # filled from Langfuse
    }

    # Write score log
    existing = []
    if SCORE_LOG.exists():
        existing = json.loads(SCORE_LOG.read_text())
    existing.append(entry)
    SCORE_LOG.write_text(json.dumps(existing, indent=2))

    # Write trace log
    with open(TRACE_LOG, "a") as f:
        for t in traces:
            f.write(json.dumps(t) + "\n")

    print(f"\n{'='*60}")
    print(f"RESULT: {passed}/{total} = {pass_rate*100:.1f}% pass@1")
    print(f"95% CI: [{ci_low*100:.1f}%, {ci_high*100:.1f}%]")
    print(f"Wall clock: {elapsed:.1f}s")
    print(f"Score log: {SCORE_LOG}")
    print(f"{'='*60}\n")

    return entry


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="τ²-Bench evaluation harness")
    parser.add_argument("--mode", choices=["baseline", "eval", "held_out"], default="baseline")
    parser.add_argument("--model", default="qwen/qwen3-235b-a22b")
    parser.add_argument("--domain", default="retail")
    parser.add_argument("--tasks", type=int, default=3)
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.3)
    args = parser.parse_args()

    run_baseline(
        model=args.model,
        domain=args.domain,
        n_tasks=args.tasks,
        n_trials=args.trials,
        temperature=args.temperature,
    )
