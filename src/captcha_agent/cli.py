"""Typer command-line interface."""

import asyncio
import argparse
import runpy
from pathlib import Path
from typing import Literal

import typer
from rich.console import Console
from rich.table import Table

from .config import load_config
from .pipeline import run as run_pipeline
from .report import verdict, write_summary

app = typer.Typer(help="Controlled CAPTCHA agent")
console = Console()


def _show_report(report) -> None:
    table = Table(title=f"Run {report.run_id}")
    table.add_column("Target")
    table.add_column("Detected")
    table.add_column("Tool")
    table.add_column("Success")
    table.add_column("Steps")
    table.add_row(
        report.target_id,
        report.detected.widget if report.detected else "unknown",
        report.attempted_tool or "-",
        "[green]verified[/green]" if report.success else "[red]failed[/red]",
        str(report.steps),
    )
    console.print(table)
    if report.reason:
        console.print(f"Reason: {report.reason}")


@app.command("run")
def run_command(
    target: str = typer.Option(..., "--target", help="Configured target ID"),
    mode: Literal["deterministic", "agent"] = typer.Option("deterministic", "--mode"),
    headed: bool = typer.Option(False, "--headed"),
    max_steps: int | None = typer.Option(None, "--max-steps", min=1),
    mock: bool = typer.Option(False, "--mock", help="Use the local no-API agent planner"),
) -> None:
    report = asyncio.run(run_pipeline(target, mode=mode, headed=headed, max_steps=max_steps, mock=mock))
    _show_report(report)
    if not report.success:
        raise typer.Exit(code=1)


@app.command("run-all")
def run_all(
    mode: Literal["deterministic", "agent"] = typer.Option("deterministic", "--mode"),
    headed: bool = typer.Option(False, "--headed"),
    max_steps: int | None = typer.Option(None, "--max-steps", min=1),
    mock: bool = typer.Option(False, "--mock", help="Use the local no-API agent planner"),
) -> None:
    config = load_config()
    reports = [
        asyncio.run(run_pipeline(target.id, mode=mode, headed=headed, max_steps=max_steps, config=config, mock=mock))
        for target in config.targets
    ]
    for report in reports:
        _show_report(report)
    summary_path = write_summary(reports, config.settings.run_dir + "/summary.md")
    console.print(f"Summary: {summary_path}")
    if any(verdict(report) not in {"PASS", "SKIPPED"} for report in reports):
        raise typer.Exit(code=1)


@app.command("measure")
def measure(
    widget: Literal["slider", "image_grid", "all"] = typer.Option("all", "--widget"),
    runs: int = typer.Option(20, "--runs", min=1),
    seed_start: int = typer.Option(1, "--seed-start"),
    live: bool = typer.Option(False, "--live"),
    port: int | None = typer.Option(None, "--port", min=1, max=65535),
    out: Path = typer.Option(Path("runs/rates.md"), "--out"),
    headed: bool = typer.Option(False, "--headed"),
) -> None:
    """Measure deterministic local fixture success rates."""
    script = Path(__file__).resolve().parents[2] / "scripts" / "measure_rates.py"
    namespace = runpy.run_path(str(script))
    args = argparse.Namespace(
        widget=widget,
        runs=runs,
        seed_start=seed_start,
        live=live,
        port=port,
        out=out,
        headed=headed,
    )
    asyncio.run(namespace["_measure"](args))


@app.command("list-targets")
def list_targets() -> None:
    table = Table(title="Configured targets")
    table.add_column("ID")
    table.add_column("URL")
    table.add_column("Expected widget")
    for target in load_config().targets:
        table.add_row(target.id, target.url, target.expected_widget)
    console.print(table)


if __name__ == "__main__":
    app()
