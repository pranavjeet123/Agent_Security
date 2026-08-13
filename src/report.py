"""Console rendering (via rich) and results/summary.json output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.scanner import ScanOutcome

console = Console()

SUMMARY_PATH = Path(__file__).resolve().parent.parent / "results" / "summary.json"


def banner() -> None:
    console.print(
        Panel.fit(
            "[bold]Azure AI Foundry Red-Teaming Demo[/bold]\n"
            "A Target agent guards a secret password. Two layers try to extract it:\n"
            "  [cyan]Layer B[/cyan] -- a live Attacker/Judge agent loop (the reliable core)\n"
            "  [cyan]Layer A[/cyan] -- Microsoft's official AI Red Teaming Agent (best-effort)",
            border_style="magenta",
        )
    )


def attacker_turn(turn_number: int, message: str) -> None:
    console.print(f"\n[bold red]Attacker (turn {turn_number}):[/bold red] {message}")


def target_turn(message: str) -> None:
    console.print(f"[bold blue]Target:[/bold blue] {message}")


def judge_line(leaked: bool, method: str, evidence: str) -> None:
    if leaked:
        console.print(f"[bold white on red] LEAK DETECTED [/bold white on red] ({method}) {evidence}")
    else:
        console.print(f"[dim]no leak ({method})[/dim]")


def layer_b_verdict(leaked: bool, turns_used: int, max_turns: int) -> None:
    if leaked:
        console.print(
            Panel.fit(
                f"[bold red]Secret leaked[/bold red] on turn {turns_used}/{max_turns}.",
                title="Layer B Verdict",
                border_style="red",
            )
        )
    else:
        console.print(
            Panel.fit(
                f"[bold green]Secret held[/bold green] after {turns_used}/{max_turns} turns.",
                title="Layer B Verdict",
                border_style="green",
            )
        )


def layer_a_result(outcome: ScanOutcome) -> None:
    if not outcome.ran:
        console.print(
            Panel(
                f"[yellow]Layer A did not run.[/yellow]\n{outcome.reason}",
                title="Layer A (Official RedTeam Scan)",
                border_style="yellow",
            )
        )
        return

    table = Table(title="Layer A (Official RedTeam Scan) Results")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Scan output", str(outcome.output_path))
    table.add_row(
        "Custom credential-leak ASR",
        f"{outcome.custom_leak_asr:.0%}" if outcome.custom_leak_asr is not None else "n/a",
    )
    table.add_row(
        "Leaked conversations",
        str(len(outcome.leaked_conversations or [])),
    )
    console.print(table)
    console.print(
        "[dim]Note: the official scorecard grades the 'sensitive_data_leakage' risk "
        "category via Azure's RAI evaluation service; the custom leak ASR above is a "
        "second, locally-computed cross-check using the same secret-match logic as "
        "Layer B.[/dim]"
    )


def write_summary(
    layer_b_leaked: bool,
    layer_b_turns: int,
    layer_b_transcript: list[dict[str, Any]],
    layer_a: ScanOutcome,
) -> None:
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "layer_b": {
            "leaked": layer_b_leaked,
            "turns_used": layer_b_turns,
            "transcript": layer_b_transcript,
        },
        "layer_a": {
            "ran": layer_a.ran,
            "reason": layer_a.reason,
            "custom_leak_asr": layer_a.custom_leak_asr,
            "leaked_conversation_count": len(layer_a.leaked_conversations or []),
        },
    }
    with open(SUMMARY_PATH, "w") as f:
        json.dump(summary, f, indent=2)
    console.print(f"\n[dim]Full summary written to {SUMMARY_PATH}[/dim]")
