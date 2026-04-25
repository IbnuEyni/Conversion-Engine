"""Wrapper to register custom agents and run τ²-Bench.

This script is called by act4_runner.py when running the policy_aware_agent.
It registers the agent with τ²-Bench's registry, then delegates to tau2 run.
"""

import sys
from pathlib import Path

# Add the eval directory to path so we can import our agent
eval_dir = Path(__file__).parent
sys.path.insert(0, str(eval_dir))

from policy_aware_agent import create_policy_aware_agent
from tau2.registry import registry
from tau2.runner.batch import run_domain
from tau2.data_model.simulation import TextRunConfig

import argparse

# Register our custom agent
registry.register_agent_factory(create_policy_aware_agent, "policy_aware_agent")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--agent-llm", required=True)
    parser.add_argument("--user-llm", required=True)
    parser.add_argument("--num-trials", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--save-to", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--log-level", default="WARNING")
    parser.add_argument("--task-ids", nargs="+", type=str)
    args = parser.parse_args()

    config = TextRunConfig(
        domain=args.domain,
        agent=args.agent,
        llm_agent=args.agent_llm,
        llm_args_agent={"temperature": 0.0},
        llm_user=args.user_llm,
        llm_args_user={"temperature": 0.0},
        num_trials=args.num_trials,
        max_steps=args.max_steps,
        timeout=args.timeout,
        max_concurrency=args.max_concurrency,
        save_to=args.save_to,
        seed=args.seed,
        log_level=args.log_level,
        task_ids=args.task_ids,
    )

    results = run_domain(config)
    return results


if __name__ == "__main__":
    main()
