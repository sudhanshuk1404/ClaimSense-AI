"""ClaimSense AI — Command Line Interface.

Usage:
    python main.py analyze                   # Analyze all denied claims
    python main.py analyze --claim CLM-2026-00142   # Single claim
    python main.py batch                     # Batch clustering report
    python main.py full                      # Run all three problems
    python main.py demo                      # Run demo with sample data, save results
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

from src.data_loader import load_claims_from_file, get_denied_claims
from src.llm_client import LLMClient
from src.denial_analyzer import DenialAnalyzer
from src.pattern_matcher import PatternMatcher
from src.batch_clusterer import BatchClusterer
from src.pipeline import ClaimSensePipeline
from src.models import Recoverability

app = typer.Typer(help="ClaimSense AI — Claim Denial Analysis System")
console = Console()

_DATA_FILE = Path("data/synthetic_claims.json")


@app.command()
def analyze(
    claim_id: str = typer.Option(None, "--claim", "-c", help="Analyze a specific claim ID only"),
    model: str = typer.Option("gpt-4o", "--model", "-m", help="OpenAI model to use"),
    output: str = typer.Option(None, "--output", "-o", help="Save JSON results to file"),
    pattern: bool = typer.Option(True, "--pattern/--no-pattern", help="Include pattern matching"),
):
    """Problem 1+2: Analyze denied claim(s) — root cause and historical patterns."""
    console.print(Panel("[bold blue]ClaimSense AI — Denial Analysis[/bold blue]"))

    pipeline = ClaimSensePipeline(model=model)
    with console.status("Running analysis..."):
        result = pipeline.run_from_file(
            data_path=_DATA_FILE,
            run_analysis=True,
            run_pattern_matching=pattern,
            run_batch=False,
            single_claim_id=claim_id,
        )

    # Display results
    for da in result.analyzed_claims:
        color = {
            Recoverability.RECOVERABLE: "green",
            Recoverability.NOT_RECOVERABLE: "red",
            Recoverability.NEEDS_REVIEW: "yellow",
        }[da.recoverability]

        console.print(Panel(
            f"[bold]{da.claim_id}[/bold]\n\n"
            f"[bold]Root Cause:[/bold] {da.denial_root_cause}\n\n"
            f"[bold]CARC Interpretation:[/bold] {da.carc_interpretation}\n\n"
            f"[bold]Recoverability:[/bold] [{color}]{da.recoverability.value}[/{color}] "
            f"(confidence: {da.confidence_score:.0%})\n\n"
            f"[bold]Rationale:[/bold] {da.recoverability_rationale}\n\n"
            f"[bold]Recommended Action:[/bold] {da.recommended_action}\n\n"
            f"[bold]Evidence:[/bold]\n" + "\n".join(f"  • {e}" for e in da.supporting_evidence),
            title=f"Claim Analysis: {da.claim_id}",
        ))

    # Pattern matching results
    for pm in result.pattern_results:
        if pm.similar_claims:
            table = Table(title=f"Similar Claims for {pm.denied_claim_id}")
            table.add_column("Claim ID")
            table.add_column("Outcome")
            table.add_column("Similarity")
            table.add_column("Match Reasons")
            for sc in pm.similar_claims:
                color = "green" if sc.outcome == "paid" else "red"
                table.add_row(
                    sc.claim_id,
                    f"[{color}]{sc.outcome}[/{color}]",
                    f"{sc.similarity_score:.2%}",
                    ", ".join(sc.match_reasons[:2]),
                )
            console.print(table)

        if pm.systemic_pattern:
            console.print(f"[yellow]Systemic Pattern:[/yellow] {pm.systemic_pattern}")
        console.print(f"[bold]Pattern Analysis:[/bold] {pm.pattern_analysis}\n")

    console.print(f"\n[dim]Session cost: ${result.session_cost_usd:.4f}[/dim]")

    if output:
        result.save(output)
        console.print(f"[green]Results saved to {output}[/green]")


@app.command()
def batch(
    model: str = typer.Option("gpt-4o", "--model", "-m", help="OpenAI model to use"),
    output: str = typer.Option(None, "--output", "-o", help="Save JSON results to file"),
):
    """Problem 3: Batch clustering — group denials and produce actionable intelligence."""
    console.print(Panel("[bold blue]ClaimSense AI — Batch Clustering Report[/bold blue]"))

    pipeline = ClaimSensePipeline(model=model)
    with console.status("Clustering denied claims..."):
        result = pipeline.run_from_file(
            data_path=_DATA_FILE,
            run_analysis=False,
            run_pattern_matching=False,
            run_batch=True,
        )

    report = result.batch_report
    if not report:
        console.print("[red]No batch report generated.[/red]")
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold]Total Claims Analyzed:[/bold] {report.total_claims_analyzed}\n"
        f"[bold]Total Denied Amount:[/bold] ${report.total_denied_amount:,.2f}\n"
        f"[bold]Clusters Found:[/bold] {len(report.clusters)}\n\n"
        f"[bold]Executive Summary:[/bold]\n{report.executive_summary}",
        title="Batch Intelligence Report",
    ))

    for cluster in report.clusters:
        is_top = cluster.cluster_id == report.top_opportunity_cluster_id
        title = f"{'⭐ ' if is_top else ''}Cluster: {cluster.label}"
        console.print(Panel(
            f"[bold]Claims:[/bold] {len(cluster.claim_ids)} | "
            f"[bold]Denied:[/bold] ${cluster.total_denied_amount:,.2f} | "
            f"[bold]Payer:[/bold] {cluster.payer or 'Mixed'} | "
            f"[bold]CARC:[/bold] {cluster.primary_carc_code or '?'}\n\n"
            f"{cluster.summary}\n\n"
            f"[bold]Action:[/bold] {cluster.recommended_action}",
            title=title,
            border_style="gold1" if is_top else "blue",
        ))

    console.print(f"\n[dim]Session cost: ${result.session_cost_usd:.4f}[/dim]")

    if output:
        result.save(output)
        console.print(f"[green]Results saved to {output}[/green]")


@app.command()
def full(
    model: str = typer.Option("gpt-4o", "--model", "-m", help="OpenAI model to use"),
    output: str = typer.Option("results/full_run.json", "--output", "-o", help="Save results"),
):
    """Run all three problems on the full dataset."""
    console.print(Panel("[bold blue]ClaimSense AI — Full Pipeline Run[/bold blue]"))
    Path("results").mkdir(exist_ok=True)

    pipeline = ClaimSensePipeline(model=model)
    with console.status("Running full pipeline (this may take a minute)..."):
        result = pipeline.run_from_file(
            data_path=_DATA_FILE,
            run_analysis=True,
            run_pattern_matching=True,
            run_batch=True,
        )

    console.print(f"[green]✓ Analyzed {len(result.analyzed_claims)} denied claims[/green]")
    console.print(f"[green]✓ Pattern matched {len(result.pattern_results)} denied claims[/green]")
    if result.batch_report:
        console.print(f"[green]✓ Identified {len(result.batch_report.clusters)} denial clusters[/green]")

    result.save(output)
    console.print(f"\n[green]Full results saved to {output}[/green]")
    console.print(f"[dim]Total session cost: ${result.session_cost_usd:.4f}[/dim]")


@app.command()
def demo(
    model: str = typer.Option("gpt-4o", "--model", "-m"),
):
    """Demonstrate the system on the 4 sample claims from the assignment brief."""
    sample_claim_ids = [
        "CLM-2026-00142",  # Timely Filing
        "CLM-2026-00287",  # Missing Information
        "CLM-2026-00391",  # Medical Necessity
        "CLM-2026-00455",  # Duplicate
    ]
    console.print(Panel("[bold blue]ClaimSense AI — Demo (Assignment Sample Claims)[/bold blue]"))

    all_claims = load_claims_from_file(_DATA_FILE)
    denied = get_denied_claims(all_claims)
    sample_denied = [c for c in denied if c.claim_id in sample_claim_ids]

    llm = LLMClient(model=model)
    analyzer = DenialAnalyzer(llm)
    matcher = PatternMatcher(llm)
    matcher.index_claims(all_claims)

    Path("results").mkdir(exist_ok=True)

    demo_output = []
    for claim in sample_denied:
        console.print(f"\n[bold cyan]Analyzing: {claim.claim_id}[/bold cyan]")

        with console.status(f"Root cause analysis..."):
            da = analyzer.analyze(claim)
        with console.status(f"Pattern matching..."):
            pm = matcher.analyze(claim)

        recov_color = {
            Recoverability.RECOVERABLE: "green",
            Recoverability.NOT_RECOVERABLE: "red",
            Recoverability.NEEDS_REVIEW: "yellow",
        }[da.recoverability]

        rprint(f"  Recoverability: [{recov_color}]{da.recoverability.value}[/{recov_color}]")
        rprint(f"  Root Cause: {da.denial_root_cause[:120]}...")
        rprint(f"  Appeal Rate: {pm.historical_appeal_success_rate:.0%}")

        demo_output.append({
            "claim_id": claim.claim_id,
            "analysis": da.model_dump(),
            "pattern": pm.model_dump(),
        })

    outfile = "results/demo_run.json"
    Path(outfile).write_text(json.dumps(demo_output, indent=2))
    console.print(f"\n[green]Demo results saved to {outfile}[/green]")
    console.print(f"[dim]Session cost: ${llm.session_cost_usd:.4f}[/dim]")


if __name__ == "__main__":
    app()
