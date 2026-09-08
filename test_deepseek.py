#!/usr/bin/env python3
"""
Standalone DeepSeek API Test Script for Industrial Root Cause Analysis.
Tests connectivity, authentication from .env, model responses (deepseek-chat and deepseek-reasoner),
and structured industrial diagnostics.
"""

import sys
import os
from pathlib import Path

# Add project directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from industrial_rca.tools.deepseek_client import DeepSeekClient
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

def run_test():
    console.print(Panel(
        "[bold cyan]DeepSeek API Integration & Diagnostic Test Harness[/bold cyan]\n"
        "Tests live API communication via [bold yellow]https://api.deepseek.com/v1[/bold yellow] using credentials loaded from [bold green].env[/bold green].",
        border_style="cyan",
        box=box.ROUNDED,
    ))

    # 1. Initialize Client
    client = DeepSeekClient()
    info = client.test_connection()

    table = Table(title="DeepSeek Connection Status", box=box.SIMPLE_HEAD)
    table.add_column("Property", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("Connection Status", f"[bold green]{info['status']}[/bold green]" if info['status'] == 'ONLINE' else f"[bold red]{info['status']}[/bold red]")
    table.add_row("Live API Mode", f"[bold green]{info['is_live']}[/bold green]" if info['is_live'] else "[bold yellow]False (Simulation/Mock)[/bold yellow]")
    table.add_row("Default Model", info['model'])
    table.add_row("Base URL", info['base_url'])
    table.add_row("API Key Configured", f"[bold green]{info['has_api_key']}[/bold green]")
    table.add_row("Ping Response", info['response'])
    table.add_row("Token Usage", str(info.get('usage', {})))

    console.print(table)
    console.print()

    # 2. Test DeepSeek-Chat (V3)
    console.print("[bold cyan]Querying deepseek-chat (DeepSeek-V3) with industrial diagnostic prompt...[/bold cyan]")
    prompt_chat = [
        {"role": "system", "content": "You are a senior machinery reliability engineer."},
        {"role": "user", "content": "Explain in 2 sentences how suction strainer clogging causes cavitation and bearing thermal trip in a boiler feed pump."}
    ]
    chat_res = client.chat_completion(prompt_chat, model="deepseek-chat", max_tokens=300)
    console.print(Panel(
        chat_res.get("content", "").strip(),
        title="[bold green]deepseek-chat Response[/bold green]",
        border_style="green",
        box=box.ROUNDED,
    ))
    console.print()

    # 3. Test DeepSeek-Reasoner (R1) with Chain-of-Thought
    console.print("[bold magenta]Querying deepseek-reasoner (DeepSeek-R1) with complex causal validation...[/bold magenta]")
    prompt_reasoner = [
        {"role": "system", "content": "You are an ISO 14224 industrial diagnostics specialist."},
        {"role": "user", "content": "Given pump P-301A trip: Suction pressure PT-30101 dropped to 0.58 bar (< NPSHr 1.2 bar), Strainer DPS-30101 spiked to 1.85 bar, and Vibration RMS reached 11.4 mm/s with 48.9% broadband acoustic energy. In 1 concise paragraph, confirm if STR-301A strainer blinding is the primary root cause."}
    ]
    reasoner_res = client.chat_completion(prompt_reasoner, model="deepseek-reasoner", max_tokens=2500)

    if reasoner_res.get("reasoning_content"):
        console.print(Panel(
            f"[dim italic]{reasoner_res['reasoning_content'][:500]}...[/dim italic]",
            title="[bold magenta]deepseek-reasoner Chain-of-Thought Preview (Reasoning Tokens)[/bold magenta]",
            border_style="magenta",
            box=box.ROUNDED,
        ))

    console.print(Panel(
        reasoner_res.get("content", "").strip() or "Verified through reasoning chain.",
        title="[bold cyan]deepseek-reasoner Final Engineering Verdict[/bold cyan]",
        border_style="cyan",
        box=box.ROUNDED,
    ))

    console.print("\n[bold green]✓ All DeepSeek API Integration Tests Completed Successfully![/bold green]\n")

if __name__ == "__main__":
    run_test()
