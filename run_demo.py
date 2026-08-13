#!/usr/bin/env python3
"""Entrypoint for the Azure AI Foundry red-teaming demo.

Usage:
    python run_demo.py [--turns N] [--keep-agent] [--skip-layer-a]
"""

from __future__ import annotations

import argparse
import asyncio

from src import attacker, judge, report, scanner, target_agent
from src.config import load_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--turns", type=int, default=6, help="Max Layer B attacker turns (default: 6)")
    parser.add_argument("--keep-agent", action="store_true", help="Don't delete the Target agent/threads at the end")
    parser.add_argument("--skip-layer-a", action="store_true", help="Skip the official RedTeam scan (Layer A)")
    return parser.parse_args()


async def run_layer_b(client, agent, openai_client, settings, max_turns: int):
    thread = target_agent.new_thread(client)
    history: list[dict] = []
    leaked = False
    turns_used = 0

    for turn in range(1, max_turns + 1):
        turns_used = turn
        attack_message = attacker.next_attack(openai_client, settings.model_deployment_name, history)
        report.attacker_turn(turn, attack_message)
        history.append({"role": "attacker", "content": attack_message})

        target_reply = target_agent.ask(client, thread.id, agent.id, attack_message)
        report.target_turn(target_reply)
        history.append({"role": "target", "content": target_reply})

        result = judge.verdict(openai_client, settings.model_deployment_name, settings.secret_value, target_reply)
        report.judge_line(result.leaked, result.method, result.evidence)

        if result.leaked:
            leaked = True
            break

    report.layer_b_verdict(leaked, turns_used, max_turns)
    return leaked, turns_used, history, [thread.id]


async def main() -> None:
    args = parse_args()
    settings = load_settings()

    report.banner()

    client = target_agent.build_client(settings)
    agent = target_agent.create_target_agent(client, settings)
    project_client = attacker.build_project_client(settings)
    openai_client = attacker.build_openai_client(project_client)

    thread_ids: list[str] = []
    try:
        leaked, turns_used, transcript, layer_b_thread_ids = await run_layer_b(
            client, agent, openai_client, settings, args.turns
        )
        thread_ids.extend(layer_b_thread_ids)

        if args.skip_layer_a:
            layer_a_outcome = scanner.ScanOutcome(ran=False, reason="Skipped via --skip-layer-a")
        else:
            layer_a_outcome = await scanner.run_scan(client, agent, settings)
        report.layer_a_result(layer_a_outcome)

        report.write_summary(leaked, turns_used, transcript, layer_a_outcome)
    finally:
        if not args.keep_agent:
            target_agent.cleanup(client, agent, thread_ids)
        project_client.close()


if __name__ == "__main__":
    asyncio.run(main())
