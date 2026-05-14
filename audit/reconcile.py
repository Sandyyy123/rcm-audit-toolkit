"""
Session-to-payment reconciliation engine.
Loads sessions, claims, and payments CSVs and produces a row-level
reconciliation matrix with gap annotations.
"""

import pandas as pd
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class ReconciliationResult:
    sessions_total: int
    claims_submitted: int
    claims_paid_full: int
    claims_paid_partial: int
    claims_denied: int
    claims_pending: int
    never_submitted: int
    revenue_at_risk: float
    matrix: pd.DataFrame


def load_sessions(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["session_date"])
    required = {"session_id", "session_date", "provider_id", "patient_id", "cpt_code", "amount_billed"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"sessions.csv missing columns: {missing}")
    return df


def load_claims(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["submitted_date"])
    required = {"claim_id", "session_id", "payer", "status", "denial_code", "amount_billed"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"claims.csv missing columns: {missing}")
    return df


def load_payments(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["payment_date"])
    required = {"payment_id", "claim_id", "amount_paid", "era_reference"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"payments.csv missing columns: {missing}")
    return df


def reconcile(
    sessions_path: Path,
    claims_path: Path,
    payments_path: Path,
    days_back: int = 90,
) -> ReconciliationResult:
    sessions = load_sessions(sessions_path)
    claims = load_claims(claims_path)
    payments = load_payments(payments_path)

    # Filter to audit window
    cutoff = pd.Timestamp.today() - pd.Timedelta(days=days_back)
    sessions = sessions[sessions["session_date"] >= cutoff].copy()

    # Merge sessions -> claims (left join to catch never-submitted)
    merged = sessions.merge(claims, on="session_id", how="left", suffixes=("_sess", "_claim"))

    # Merge in payments
    merged = merged.merge(payments, on="claim_id", how="left")

    # Classify each row
    def classify(row):
        if pd.isna(row.get("claim_id")):
            return "never_submitted"
        if row.get("status") == "denied":
            return "denied"
        if row.get("status") == "pending":
            return "pending"
        if pd.notna(row.get("amount_paid")):
            if row["amount_paid"] >= row["amount_billed_sess"] * 0.95:
                return "paid_full"
            return "paid_partial"
        return "pending"

    merged["reconciliation_status"] = merged.apply(classify, axis=1)

    counts = merged["reconciliation_status"].value_counts().to_dict()

    revenue_at_risk = merged.loc[
        merged["reconciliation_status"].isin(["denied", "pending", "never_submitted"]),
        "amount_billed_sess",
    ].sum()

    return ReconciliationResult(
        sessions_total=len(sessions),
        claims_submitted=int(counts.get("paid_full", 0) + counts.get("paid_partial", 0) + counts.get("denied", 0) + counts.get("pending", 0)),
        claims_paid_full=int(counts.get("paid_full", 0)),
        claims_paid_partial=int(counts.get("paid_partial", 0)),
        claims_denied=int(counts.get("denied", 0)),
        claims_pending=int(counts.get("pending", 0)),
        never_submitted=int(counts.get("never_submitted", 0)),
        revenue_at_risk=float(revenue_at_risk),
        matrix=merged,
    )
