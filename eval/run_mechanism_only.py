#!/usr/bin/env python3
"""Run mechanism only on 30 tasks, compare against existing baseline."""

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
TAU2_PYTHON = TAU2_DIR / ".venv" / "bin" / "python"
RESULTS_DIR = EVAL_DIR / "tau2_results"
MODEL = "openrouter/openai/gpt-4.1"
TASK_IDS = list(range(0, 30))


def wilson_ci95(s, n):
    if n == 0: return 0, 0, 0
    p, z = s/n, 1.96
    d = 1 + z**2/n
    c = (p + z**2/(2*n)) / d
    sp = z * math.sqrt((p*(1-p) + z**2/(4*n))/n) / d
    return p, max(0, c-sp), min(1, c+sp)


def parse_results(path):
    results_file = path / "results.json" if path.is_dir() else path
    if not results_file.exists(): return []
    data = json.loads(results_file.read_text())
    out = []
    for sim in data.get("simulations", []):
        ri = sim.get("reward_info") or {}
        reward = ri.get("reward", 0)
        msgs = sim.get("messages", [])
        at, ut = 0, 0
        for m in msgs:
            u = m.get("usage") or {}
            at += u.get("completion_tokens", 0)
            ut += u.get("prompt_tokens", 0)
        out.append({
            "task_id": sim.get("task_id", ""),
            "trial": sim.get("trial", 0),
            "reward": reward,
            "n_messages": len(msgs),
            "agent_tokens": at,
            "user_tokens": ut,
            "wall_clock_s": sim.get("duration", 0),
        })
    return out


# Load existing baseline
print("Loading existing baseline from held_out_traces.jsonl...")
bl_traces = []
with open(EVAL_DIR / "held_out_traces.jsonl") as f:
    for line in f:
        t = json.loads(line)
        if t.get("label") == "dev_gpt41_baseline":
            bl_traces.append(t)

bl_passed = sum(1 for t in bl_traces if t.get("passed"))
bl_total = len(bl_traces)
bl_p, bl_ci_lo, bl_ci_hi = wilson_ci95(bl_passed, bl_total)
print(f"Baseline: {bl_passed}/{bl_total} = {bl_p*100:.1f}% [{bl_ci_lo*100:.1f}%, {bl_ci_hi*100:.1f}%]")

# Run mechanism on 30 tasks
save_path = RESULTS_DIR / f"dev_gpt41_mechanism_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl"

cmd = [
    str(TAU2_PYTHON),
    str(EVAL_DIR / "_run_with_agent.py"),
    "--domain", "retail",
    "--agent", "policy_aware_agent",
    "--agent-llm", MODEL,
    "--user-llm", MODEL,
    "--num-trials", "1",
    "--max-steps", "30",
    "--timeout", "300",
    "--max-concurrency", "1",
    "--save-to", str(save_path),
    "--seed", "42",
    "--log-level", "WARNING",
    "--task-ids",
] + [str(t) for t in TASK_IDS]

env = {**os.environ, "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", "")}

print(f"\nRunning mechanism on {len(TASK_IDS)} tasks...")
print(f"Save to: {save_path}")
start = time.time()
proc = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=str(TAU2_DIR))
elapsed = time.time() - start

if proc.stdout:
    for line in proc.stdout.strip().split("\n")[-15:]:
        print(line)
if proc.returncode != 0 and proc.stderr:
    errors = [l for l in proc.stderr.strip().split("\n") if "ERROR" in l and "model isn't mapped" not in l]
    if errors:
        for e in errors[-5:]:
            print(f"ERROR: {e}")

# Parse mechanism results
mech_results = parse_results(save_path)
m_passed = sum(1 for r in mech_results if r.get("reward", 0) > 0)
m_total = len(mech_results)
m_p, m_ci_lo, m_ci_hi = wilson_ci95(m_passed, m_total)
m_tokens = sum(r.get("agent_tokens", 0) + r.get("user_tokens", 0) for r in mech_results)

print(f"\n{'='*60}")
print(f"Mechanism: {m_passed}/{m_total} = {m_p*100:.1f}% [{m_ci_lo*100:.1f}%, {m_ci_hi*100:.1f}%]")
print(f"Baseline:  {bl_passed}/{bl_total} = {bl_p*100:.1f}% [{bl_ci_lo*100:.1f}%, {bl_ci_hi*100:.1f}%]")

# Fisher exact
table = [[m_passed, m_total - m_passed], [bl_passed, bl_total - bl_passed]]
_, p_val = stats.fisher_exact(table, alternative="greater")
delta = m_p - bl_p

print(f"Delta A: {delta*100:+.1f}%  p={p_val:.4f}  significant={'YES' if p_val < 0.05 else 'NO'}")
print(f"Wall clock: {elapsed:.0f}s ({elapsed/60:.1f}m)")
print(f"{'='*60}")

# Write traces
traces_path = EVAL_DIR / "held_out_traces.jsonl"
# Keep existing baseline + instructor, remove old mechanism
existing = []
with open(traces_path) as f:
    for line in f:
        t = json.loads(line)
        if t.get("label") != "dev_gpt41_mechanism":
            existing.append(line.strip())

with open(traces_path, "w") as f:
    for line in existing:
        f.write(line + "\n")
    for r in mech_results:
        trace = {
            "trace_id": f"act4_dev_gpt41_mechanism_{r['task_id']}_{r['trial']}",
            "type": "tau2_eval",
            "task_id": r["task_id"],
            "trial": r["trial"],
            "reward": r["reward"],
            "passed": r["reward"] > 0,
            "n_messages": r["n_messages"],
            "agent_tokens": r["agent_tokens"],
            "user_tokens": r["user_tokens"],
            "total_cost": 0,
            "wall_clock_s": round(r.get("wall_clock_s", 0), 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "label": "dev_gpt41_mechanism",
            "agent": "policy_aware_agent",
            "model": MODEL,
        }
        f.write(json.dumps(trace) + "\n")

print(f"Updated {traces_path}")

# Update ablation_results.json
bl_tokens = sum(t.get("agent_tokens", 0) + t.get("user_tokens", 0) for t in bl_traces)
bl_cost = sum(t.get("user_tokens", 0) for t in bl_traces) * 2/1e6 + sum(t.get("agent_tokens", 0) for t in bl_traces) * 8/1e6
m_cost = sum(r.get("user_tokens", 0) for r in mech_results) * 2/1e6 + sum(r.get("agent_tokens", 0) for r in mech_results) * 8/1e6

ablation = {
    "comparison": {
        "task_ids": TASK_IDS,
        "num_trials": 1,
        "model": MODEL,
        "domain": "retail",
    },
    "baseline": {
        "agent": "llm_agent",
        "description": "Default tau2-bench LLM agent, gpt-4.1 via OpenRouter",
        "pass_at_1": round(bl_p, 4),
        "ci_95_low": round(bl_ci_lo, 4),
        "ci_95_high": round(bl_ci_hi, 4),
        "passed": bl_passed,
        "total": bl_total,
        "total_tokens": bl_tokens,
        "cost_per_task_usd": round(bl_cost / max(bl_total, 1), 4),
        "p95_latency_s": 49.06,
    },
    "mechanism": {
        "agent": "policy_aware_agent",
        "description": "Enhanced system prompt with auth-first, confirm-before-write, follow-policy rules",
        "pass_at_1": round(m_p, 4),
        "ci_95_low": round(m_ci_lo, 4),
        "ci_95_high": round(m_ci_hi, 4),
        "passed": m_passed,
        "total": m_total,
        "wall_clock_s": round(elapsed, 2),
        "total_tokens": m_tokens,
        "cost_per_task_usd": round(m_cost / max(m_total, 1), 4),
        "p95_latency_s": round(sorted([r.get("wall_clock_s", 0) for r in mech_results])[int(0.95 * len(mech_results)) - 1], 2) if mech_results else 0,
    },
    "automated_optimization_baseline": {
        "agent": "llm_agent",
        "description": "Instructor-provided reference, gpt-4.1 direct OpenAI, 30 tasks x 5 trials",
        "pass_at_1": 0.7267,
        "ci_95_low": 0.6504,
        "ci_95_high": 0.7917,
        "passed": 109,
        "total": 150,
        "cost_per_task_usd": 0.0199,
        "p95_latency_s": 551.65,
    },
    "delta_a": {
        "value": round(delta, 4),
        "description": "mechanism pass@1 - baseline pass@1",
        "positive": bool(delta > 0),
        "p_value": round(float(p_val), 6),
        "significant_at_005": bool(p_val < 0.05),
        "test": "fisher_exact_one_sided",
    },
    "timestamp": datetime.now(timezone.utc).isoformat(),
}

abl_path = EVAL_DIR / "ablation_results.json"
abl_path.write_text(json.dumps(ablation, indent=2))
print(f"Updated {abl_path}")
print("\nDone!")
