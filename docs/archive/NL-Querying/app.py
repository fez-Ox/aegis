#!/usr/bin/env python3
"""Interactive Terminal Application for Aegis Spatio-Temporal Memory.

Provides an interactive CLI / REPL interface where you can:
1. Ingest a video to Modal to reconstruct 3D space and build spatio-temporal memory.
2. Ask natural language questions ("where is my laptop", "where did I leave my phone").
3. Get dementia-friendly, evidence-grounded answers powered by a closed 525+ item
   household vocabulary and local Ollama Qwen (qwen2.5:1.5b) as an escape hatch.

Examples::

    # Launch interactive terminal app
    uv run python "NL Querying/app.py"

    # Start with a specific dataset or Modal transport
    uv run python "NL Querying/app.py" --transport modal --dataset nlq_sample

    # Send a video to Modal and jump directly into questioning
    uv run python "NL Querying/app.py" --video "NL Querying/sample_input_video.mp4" --dataset my_room

    # One-shot command line query
    uv run python "NL Querying/app.py" --ask "where is my laptop" --dataset nlq_sample
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Bootstrap package root
FOLDER_ROOT = Path(__file__).resolve().parent
REPO_ROOT = FOLDER_ROOT.parent
if str(FOLDER_ROOT) not in sys.path:
    sys.path.insert(0, str(FOLDER_ROOT))

from comm.client import AegisCommClient
from comm.transports import (
    DatasetNotFoundError,
    TransportError,
    create_source,
)
from nlq.dictionary import DictionaryIndex
from nlq.engine import AskResult, HybridNLQEngine

# Rich UI components
try:
    from rich.box import ROUNDED
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    HAS_RICH = True
    console = Console()
except ImportError:  # pragma: no cover
    HAS_RICH = False
    console = None  # type: ignore[assignment]


def print_banner(
    dataset_id: str | None,
    transport_name: str,
    llm_info: dict[str, Any],
    dict_stats: dict[str, int],
) -> None:
    """Print the Aegis terminal header and current system status."""
    if not HAS_RICH:
        print("\n" + "=" * 65)
        print("          AEGIS — Spatio-Temporal Memory Terminal")
        print("=" * 65)
        print(f"Dataset:    {dataset_id or 'None'}")
        print(f"Transport:  {transport_name}")
        print(
            f"Local LLM:  {llm_info.get('model', 'none')} ({'ready' if llm_info.get('available') else 'offline'})"
        )
        print(
            f"Vocabulary: {dict_stats.get('canonical', 0)} items / {dict_stats.get('synonyms', 0)} aliases"
        )
        print("=" * 65 + "\n")
        return

    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="right", ratio=1)

    llm_status = (
        f"[green]● {llm_info.get('model')}[/green] ([dim]{llm_info.get('provider')}[/dim])"
        if llm_info.get("available")
        else "[yellow]○ disabled / offline[/yellow]"
    )

    left_text = Text.from_markup(
        f"[bold cyan]Aegis Spatio-Temporal Memory[/bold cyan]\n"
        f"[dim]Active Dataset:[/dim] [bold white]{dataset_id or 'No dataset loaded'}[/bold white]\n"
        f"[dim]Transport:[/dim] [magenta]{transport_name}[/magenta]"
    )
    right_text = Text.from_markup(
        f"[dim]Local LLM:[/dim] {llm_status}\n"
        f"[dim]Vocabulary:[/dim] [bold]{dict_stats.get('canonical', 0)}[/bold] items / [bold]{dict_stats.get('synonyms', 0)}[/bold] aliases\n"
        f"[dim]Type [bold white]/help[/bold white] for commands, [bold white]/exit[/bold white] to quit[/dim]"
    )
    grid.add_row(left_text, right_text)

    panel = Panel(
        grid,
        title="[bold yellow]🛡️  AEGIS TERMINAL ASSISTANT [/bold yellow]",
        subtitle="[dim]Egocentric Video 3D Memory & Natural Language Recall[/dim]",
        border_style="cyan",
        box=ROUNDED,
    )
    console.print(panel)


def ingest_video_to_modal(
    video_path: str | Path,
    dataset_id: str,
    gpu: str = "cpu",
    vggt_model: str = "wincentIsMe/VGGT-Omega",
) -> bool:
    """Run pipeline on Modal and sync generated artifacts locally."""
    video_file = Path(video_path).resolve()
    if not video_file.is_file():
        if HAS_RICH:
            console.print(
                f"[bold red]Error:[/bold red] Video file not found: {video_file}"
            )
        else:
            print(f"Error: Video file not found: {video_file}")
        return False

    if HAS_RICH:
        console.print(
            Panel(
                f"[bold cyan]Submitting Video to Modal Pipeline[/bold cyan]\n"
                f"[dim]Video:[/dim]      {video_file.name} ({round(video_file.stat().st_size / (1024 * 1024), 2)} MB)\n"
                f"[dim]Dataset ID:[/dim] {dataset_id}\n"
                f"[dim]Compute:[/dim]    Modal {gpu.upper()}\n"
                f"[dim]Model:[/dim]      {vggt_model}",
                title="[yellow]Ingestion Launch[/yellow]",
                border_style="yellow",
            )
        )
    else:
        print(
            f"Submitting {video_file.name} to Modal pipeline (dataset: {dataset_id}, compute: {gpu})..."
        )

    # Run build_memory.py or run_pipeline.py
    cmd = [
        sys.executable,
        "-m",
        "modal",
        "run",
        "run_pipeline.py",
        "--video",
        str(video_file),
        "--dataset-id",
        dataset_id,
        "--stage",
        "all",
        "--vggt-model",
        vggt_model,
        "--keyframe-stride",
        "10",
    ]

    env = dict(os.environ)
    if gpu:
        env["AEGIS_GPU"] = gpu
    if "i230683" not in env.get("MODAL_PROFILE", ""):
        env.setdefault("MODAL_PROFILE", "i230683")

    start_time = time.time()
    try:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, check=False)
        if proc.returncode != 0:
            if HAS_RICH:
                console.print(
                    f"[bold red]Pipeline failed with exit code {proc.returncode}[/bold red]"
                )
            else:
                print(f"Pipeline failed with exit code {proc.returncode}")
            return False
    except (OSError, subprocess.SubprocessError) as exc:
        if HAS_RICH:
            console.print(
                f"[bold red]Failed to execute modal command:[/bold red] {exc}"
            )
        else:
            print(f"Failed to execute modal command: {exc}")
        return False

    duration = round(time.time() - start_time, 1)

    # Sync downloaded outputs to NL Querying/outputs/<dataset_id>
    src_outputs = REPO_ROOT / "outputs" / dataset_id
    dst_outputs = FOLDER_ROOT / "outputs" / dataset_id
    if src_outputs.is_dir():
        import shutil

        shutil.copytree(src_outputs, dst_outputs, dirs_exist_ok=True)
        if HAS_RICH:
            console.print(
                f"[bold green]✓ Pipeline completed in {duration}s! Synced artifacts to {dst_outputs.relative_to(REPO_ROOT)}[/bold green]"
            )
        else:
            print(
                f"Pipeline completed in {duration}s! Synced artifacts to {dst_outputs}"
            )
    else:
        if HAS_RICH:
            console.print(
                f"[yellow]Pipeline completed in {duration}s. Artifacts on Modal volume.[/yellow]"
            )
        else:
            print(f"Pipeline completed in {duration}s.")
    return True


def display_scene_summary(client: AegisCommClient, dataset_id: str) -> None:
    """Print a structured breakdown of the active memory scene."""
    try:
        summary = client.scene_summary(dataset_id)
    except (TransportError, KeyError, ValueError) as exc:
        if HAS_RICH:
            console.print(f"[bold red]Could not load scene summary:[/bold red] {exc}")
        else:
            print(f"Could not load scene summary: {exc}")
        return

    if not HAS_RICH:
        print("\n--- Scene Summary ---")
        print(f"Dataset:  {summary.get('dataset_id')}")
        print(f"Rooms:    {', '.join(summary.get('rooms', [])) or 'None'}")
        print(f"Anchors:  {', '.join(summary.get('anchors', [])) or 'None'}")
        print(f"Objects:  {', '.join(summary.get('tracked_objects', [])) or 'None'}")
        print(f"Events:   {summary.get('num_events', 0)}")
        print(f"Frames:   {summary.get('timeline_frames', 0)}\n")
        return

    table = Table(
        title=f"Scene Memory Breakdown — [bold white]{dataset_id}[/bold white]",
        box=ROUNDED,
    )
    table.add_column("Category", style="cyan", width=18)
    table.add_column("Elements Detected & Grounded", style="white")

    rooms = summary.get("rooms", [])
    anchors = summary.get("anchors", [])
    objects = summary.get("tracked_objects", [])

    table.add_row("Rooms (Zones)", ", ".join(rooms) if rooms else "[dim]None[/dim]")
    table.add_row(
        "Spatial Anchors", ", ".join(anchors) if anchors else "[dim]None[/dim]"
    )
    table.add_row(
        "Tracked Objects (3D)", ", ".join(objects) if objects else "[dim]None[/dim]"
    )
    table.add_row(
        "Trajectory & Events",
        f"{summary.get('num_events', 0)} state transitions across {summary.get('timeline_frames', 0)} keyframes",
    )

    console.print(table)


def display_answer(result: AskResult) -> None:
    """Render the NLQ answer card."""
    if not HAS_RICH:
        print("\n" + "-" * 50)
        print(f"Q: {result.query}")
        print(f"A: {result.answer_text}")
        if result.found:
            print(
                f"   [Grounded: {result.instance_label} in {result.room_label} on {result.anchor_label} ({result.relation})]"
            )
        elif result.suggestions:
            print(f"   [Suggestions: {', '.join(result.suggestions)}]")
        if result.llm_used:
            print("   [Resolved via Local LLM Escape Hatch]")
        print("-" * 50 + "\n")
        return

    # Color coded status
    if result.found:
        status_color = "green"
        status_icon = "✓"
        box_style = ROUNDED
    elif result.abstained:
        status_color = "yellow"
        status_icon = "ℹ"
        box_style = ROUNDED
    else:
        status_color = "red"
        status_icon = "✗"
        box_style = ROUNDED

    lines: list[str] = [
        f"[bold {status_color}]{status_icon} {result.answer_text}[/bold {status_color}]\n"
    ]

    details: list[str] = []
    if result.found:
        details.append(
            f"[dim]Object:[/dim] [bold white]{result.instance_label}[/bold white]"
        )
        if result.room_label:
            details.append(
                f"[dim]Room:[/dim] [bold cyan]{result.room_label}[/bold cyan]"
            )
        if result.anchor_label:
            details.append(
                f"[dim]Anchor:[/dim] [bold yellow]{result.anchor_label}[/bold yellow]"
            )
        if result.relation:
            details.append(f"[dim]Relation:[/dim] [magenta]{result.relation}[/magenta]")
        if result.last_seen_timestamp:
            details.append(f"[dim]Timestamp:[/dim] {result.last_seen_timestamp:.1f}s")
    elif result.suggestions:
        details.append(
            f"[dim]Did you mean:[/dim] [cyan]{', '.join(result.suggestions)}[/cyan]"
        )
    elif result.abstain_reason:
        details.append(
            f"[dim]Status:[/dim] [dim italic]{result.abstain_reason}[/dim italic]"
        )

    if result.llm_used:
        details.append(
            "[dim]Audit:[/dim] [bold green]Mapped by Ollama Qwen escape hatch[/bold green]"
        )
    else:
        details.append(
            "[dim]Audit:[/dim] [dim]Direct dictionary match (no LLM needed)[/dim]"
        )

    if details:
        lines.append(" · ".join(details))

    content = "\n".join(lines)
    panel = Panel(
        content,
        title=f"[dim]Query:[/dim] [bold]{result.query}[/bold]",
        subtitle=f"[dim]Intent: {result.intent.value.upper()}[/dim]",
        border_style=status_color,
        box=box_style,
    )
    console.print(panel)


def display_vocab_search(dictionary: DictionaryIndex, search_term: str | None) -> None:
    """Search or summarize the closed household vocabulary."""
    all_items = dictionary.item_synonyms
    all_rooms = dictionary.room_keywords

    if not search_term:
        msg = (
            f"The closed household vocabulary contains [bold cyan]{len(all_items)}[/bold cyan] canonical items, "
            f"[bold cyan]{sum(len(v) for v in all_items.values())}[/bold cyan] aliases, and "
            f"[bold cyan]{len(all_rooms)}[/bold cyan] rooms.\n"
            "Use [bold white]/vocab <term>[/bold white] to check if an item or alias is supported."
        )
        if HAS_RICH:
            console.print(
                Panel(msg, title="Closed Household Vocabulary", border_style="cyan")
            )
        else:
            print(msg)
        return

    term = search_term.lower().strip()
    matches: list[tuple[str, list[str]]] = []
    for canonical, synonyms in all_items.items():
        if term in canonical or any(term in syn for syn in synonyms):
            matches.append((canonical, synonyms))

    if not matches:
        if HAS_RICH:
            console.print(
                f"[yellow]No items matching '{term}' found in the closed vocabulary.[/yellow]"
            )
        else:
            print(f"No items matching '{term}' found in the closed vocabulary.")
        return

    if not HAS_RICH:
        print(f"Matches for '{term}':")
        for canon, syns in matches[:10]:
            print(f"  - {canon}: {', '.join(syns)}")
        return

    table = Table(
        title=f"Vocabulary Matches for '[bold cyan]{term}[/bold cyan]'", box=ROUNDED
    )
    table.add_column("Canonical Item", style="bold white", width=22)
    table.add_column("Recognized Aliases / Synonyms", style="dim")
    for canon, syns in matches[:15]:
        table.add_row(canon, ", ".join(syns))
    console.print(table)


def run_repl(
    engine: HybridNLQEngine,
    client: AegisCommClient,
    current_dataset: str,
    transport_name: str,
    gpu: str = "cpu",
) -> None:
    """Main interactive REPL loop."""
    dict_stats = {
        "canonical": len(engine.dictionary.item_synonyms),
        "synonyms": sum(len(v) for v in engine.dictionary.item_synonyms.values()),
    }
    llm_info = engine.llm_status()

    print_banner(current_dataset, transport_name, llm_info, dict_stats)
    display_scene_summary(client, current_dataset)

    while True:
        try:
            if HAS_RICH:
                prompt_str = f"[bold cyan]aegis[/bold cyan] [dim]([white]{current_dataset}[/white])[/dim] [bold yellow]>[/bold yellow] "
                raw_input = console.input(prompt_str).strip()
            else:
                raw_input = input(f"aegis ({current_dataset}) > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting Aegis terminal. Goodbye!")
            break

        if not raw_input:
            continue

        lower_input = raw_input.lower()

        # Handle commands
        if lower_input in {"/exit", "/quit", "exit", "quit"}:
            if HAS_RICH:
                console.print("[dim]Exiting Aegis terminal. Take care![/dim]")
            else:
                print("Exiting Aegis terminal. Take care!")
            break

        if lower_input in {"/help", "help", "/?"}:
            help_text = (
                "[bold cyan]Available Commands:[/bold cyan]\n"
                "  [bold white]/summary[/bold white]               Show 3D scene breakdown (rooms, anchors, objects)\n"
                "  [bold white]/datasets[/bold white]              List available datasets\n"
                "  [bold white]/switch <dataset_id>[/bold white]  Switch active memory dataset\n"
                "  [bold white]/ingest <video_path>[/bold white]  Upload & reconstruct video on Modal\n"
                "  [bold white]/vocab [search_term][/bold white] Check supported household vocabulary\n"
                "  [bold white]/history[/bold white]               View recent queries and audit trace\n"
                "  [bold white]/exit[/bold white]                  Quit the application\n\n"
                "[bold cyan]Example Questions:[/bold cyan]\n"
                "  • [italic]Where is my laptop?[/italic]\n"
                "  • [italic]Where did I leave my phone?[/italic]\n"
                "  • [italic]Where are my kicks?[/italic] (tests slang via local Ollama Qwen)\n"
                "  • [italic]Where is my water bottle?[/italic]\n"
                "  • [italic]Where are my glasses in the bedroom?[/italic]"
            )
            if HAS_RICH:
                console.print(
                    Panel(help_text, title="Help & Commands", border_style="cyan")
                )
            else:
                print(help_text)
            continue

        if lower_input in {"/summary", "/info"}:
            display_scene_summary(client, current_dataset)
            continue

        if lower_input == "/datasets":
            datasets = client.list_datasets()
            if HAS_RICH:
                ds_list = ", ".join(
                    f"[bold white]{d}[/bold white]" if d == current_dataset else d
                    for d in datasets
                )
                console.print(f"[dim]Available datasets:[/dim] {ds_list}")
            else:
                print(f"Available datasets: {', '.join(datasets)}")
            continue

        if lower_input.startswith("/switch"):
            parts = raw_input.split(maxsplit=1)
            if len(parts) < 2:
                if HAS_RICH:
                    console.print("[yellow]Usage: /switch <dataset_id>[/yellow]")
                else:
                    print("Usage: /switch <dataset_id>")
                continue
            new_dataset = parts[1].strip()
            try:
                # Pre-load to verify it exists
                client.load_memory(new_dataset)
                current_dataset = new_dataset
                if HAS_RICH:
                    console.print(
                        f"[bold green]Switched to dataset '{current_dataset}'[/bold green]"
                    )
                else:
                    print(f"Switched to dataset '{current_dataset}'")
                display_scene_summary(client, current_dataset)
            except DatasetNotFoundError:
                if HAS_RICH:
                    console.print(
                        f"[bold red]Dataset '{new_dataset}' not found.[/bold red]"
                    )
                else:
                    print(f"Dataset '{new_dataset}' not found.")
            continue

        if lower_input.startswith("/vocab"):
            parts = raw_input.split(maxsplit=1)
            search_arg = parts[1].strip() if len(parts) > 1 else None
            display_vocab_search(engine.dictionary, search_arg)
            continue

        if lower_input == "/history":
            log = engine.query_log
            if not log:
                if HAS_RICH:
                    console.print("[dim]No queries recorded in this session yet.[/dim]")
                else:
                    print("No queries recorded in this session yet.")
                continue
            if HAS_RICH:
                table = Table(title="Recent Query Audit Log", box=ROUNDED)
                table.add_column("Query", style="white")
                table.add_column("Result", style="cyan")
                table.add_column("LLM Used", style="dim")
                for entry in log[-8:]:
                    table.add_row(
                        entry.get("query", ""),
                        entry.get("answer", "")[:45] + "...",
                        "[green]Yes[/green]"
                        if entry.get("llm_used")
                        else "[dim]No[/dim]",
                    )
                console.print(table)
            else:
                for entry in log[-8:]:
                    print(f"- Q: {entry.get('query')} -> {entry.get('answer')}")
            continue

        if lower_input.startswith("/ingest"):
            parts = raw_input.split()
            if len(parts) < 2:
                if HAS_RICH:
                    console.print(
                        "[yellow]Usage: /ingest <path_to_video> [optional_dataset_id][/yellow]"
                    )
                else:
                    print("Usage: /ingest <path_to_video> [optional_dataset_id]")
                continue
            video_arg = parts[1]
            new_id = (
                parts[2]
                if len(parts) > 2
                else f"video_{Path(video_arg).stem}_{int(time.time()) % 10000}"
            )
            success = ingest_video_to_modal(video_arg, new_id, gpu=gpu)
            if success:
                client.clear_cache(new_id)
                current_dataset = new_id
                display_scene_summary(client, current_dataset)
            continue

        # Regular natural language question
        try:
            if HAS_RICH:
                with console.status(
                    "[bold cyan]Querying spatio-temporal memory...[/bold cyan]"
                ):
                    result = engine.ask(raw_input, current_dataset)
            else:
                result = engine.ask(raw_input, current_dataset)
            display_answer(result)
        except (TransportError, RuntimeError, ValueError) as exc:
            if HAS_RICH:
                console.print(f"[bold red]Query failed:[/bold red] {exc}")
            else:
                print(f"Query failed: {exc}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aegis Interactive Spatio-Temporal Terminal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--video",
        default=None,
        help="Optional input video to ingest to Modal before starting questioning.",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Dataset identifier to query (default: nlq_sample or first available).",
    )
    parser.add_argument(
        "--transport",
        choices=["auto", "local", "modal"],
        default="auto",
        help="Communication channel override (default: auto).",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Modal endpoint base URL override.",
    )
    parser.add_argument(
        "--gpu",
        choices=["cpu", "l4", "t4", "a10g"],
        default="cpu",
        help="Compute target for Modal video pipeline (default: cpu).",
    )
    parser.add_argument(
        "--ask",
        default=None,
        help="Run a single question non-interactively and exit.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable the local Ollama LLM escape hatch.",
    )
    args = parser.parse_args(argv)

    # If video specified, ingest it first
    dataset_id = args.dataset
    if args.video:
        dataset_id = (
            dataset_id or f"run_{Path(args.video).stem}_{int(time.time()) % 10000}"
        )
        success = ingest_video_to_modal(args.video, dataset_id, gpu=args.gpu)
        if not success and not args.dataset:
            return 1

    try:
        source = create_source(transport=args.transport, base_url=args.base_url)
        client = AegisCommClient(source=source)
        engine = HybridNLQEngine(client=client, llm=None if args.no_llm else "auto")

        datasets = client.list_datasets()
        if not dataset_id:
            if "nlq_sample" in datasets:
                dataset_id = "nlq_sample"
            elif datasets:
                dataset_id = datasets[0]
            else:
                dataset_id = "demo01"

        # One-shot mode if --ask provided
        if args.ask:
            result = engine.ask(args.ask, dataset_id)
            display_answer(result)
            return 0

        # Launch interactive REPL
        run_repl(
            engine=engine,
            client=client,
            current_dataset=dataset_id,
            transport_name=source.transport,
            gpu=args.gpu,
        )
        return 0
    except TransportError as exc:
        if HAS_RICH:
            console.print(f"[bold red]Communication failure:[/bold red] {exc}")
        else:
            print(f"Communication failure: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
