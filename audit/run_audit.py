"""
Main audit runner. Orchestrates reconcile, claims analysis, TIQ audit, and report generation.

Usage:
    python audit/run_audit.py --data sample_data/ --output reports/ --days 90
"""

import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table

from reconcile import reconcile
from claims_analyzer import analyze_denials, analyze_cpt_leakage
from tiq_parser import run_tiq_audit

console = Console()
app = typer.Typer()


@app.command()
def main(
    data: Path = typer.Option(..., help="Directory with sessions/claims/payments/patients CSVs"),
    output: Path = typer.Option(Path("reports/"), help="Output directory for reports"),
    days: int = typer.Option(90, help="Audit window in days"),
):
    output.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold purple]Revenue Cycle Audit[/bold purple] - last {days} days")
    console.print(f"Data: {data} | Output: {output}\n")

    # Step 1: Reconciliation
    console.print("[cyan]Step 1/3: Session-to-payment reconciliation...[/cyan]")
    result = reconcile(
        sessions_path=data / "sessions.csv",
        claims_path=data / "claims.csv",
        payments_path=data / "payments.csv",
        days_back=days,
    )

    t = Table(title="Reconciliation Summary")
    t.add_column("Metric")
    t.add_column("Value", justify="right")
    t.add_row("Sessions", str(result.sessions_total))
    t.add_row("Claims submitted", str(result.claims_submitted))
    t.add_row("Paid (full)", str(result.claims_paid_full))
    t.add_row("Paid (partial)", str(result.claims_paid_partial))
    t.add_row("Denied", f"[red]{result.claims_denied}[/red]")
    t.add_row("Never submitted", f"[red]{result.never_submitted}[/red]")
    t.add_row("Revenue at risk", f"[yellow]${result.revenue_at_risk:,.0f}[/yellow]")
    console.print(t)

    # Export matrix
    matrix_path = output / "reconciliation_matrix.xlsx"
    result.matrix.to_excel(matrix_path, index=False)
    console.print(f"  Saved: {matrix_path}")

    # Step 2: Claims analysis
    console.print("\n[cyan]Step 2/3: Claims denial analysis...[/cyan]")
    import pandas as pd
    claims = pd.read_csv(data / "claims.csv")
    sessions = pd.read_csv(data / "sessions.csv")
    denial_results = analyze_denials(claims)

    if denial_results["top_issues"]:
        console.print("[bold]Top denial codes:[/bold]")
        for issue in denial_results["top_issues"]:
            color = "red" if issue["severity"] == "Critical" else "yellow"
            console.print(f"  [{color}]{issue['code']}[/{color}] {issue['description']} - {issue['count']} claims (${issue['amount_at_risk']:,.0f})")

    claims_path = output / "claims_analysis.xlsx"
    denial_results["denial_codes"].to_excel(claims_path, index=False)
    console.print(f"  Saved: {claims_path}")

    # Step 3: TIQ audit
    console.print("\n[cyan]Step 3/3: TIQ system audit...[/cyan]")
    tiq = run_tiq_audit(
        patients_path=data / "patients.csv",
        payments_path=data / "payments.csv",
        claims_path=data / "claims.csv",
    )

    console.print(f"  Avg days to payment: [yellow]{tiq.avg_days_to_payment}[/yellow]")
    console.print(f"  Cash float (manual collection): [yellow]${tiq.float_amount:,.0f}[/yellow]")
    for gap in tiq.reporting_gaps:
        console.print(f"  [red]Gap:[/red] {gap}")

    tiq_path = output / "tiq_audit.xlsx"
    tiq.autopay_rates.to_excel(tiq_path, index=False)
    console.print(f"  Saved: {tiq_path}")

    console.print(f"\n[bold green]Audit complete.[/bold green] Reports in {output}/")
    console.print("Run report_generator.py to build the HTML diagnostic report.")


if __name__ == "__main__":
    app()
