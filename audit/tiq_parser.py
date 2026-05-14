"""
TIQ (and generic practice management system) export parser.
Audits autopay enrollment rates, ERA posting coverage, and reporting gaps by payer.
"""

import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TIQAuditResult:
    autopay_rates: pd.DataFrame           # payer -> autopay enrollment %
    era_coverage: pd.DataFrame            # payer -> ERA posting mode (auto/manual/missing)
    reporting_gaps: list[str]             # human-readable gap descriptions
    avg_days_to_payment: Optional[float]
    float_amount: float                   # estimated cash in transit due to manual collection


def audit_autopay(patients: pd.DataFrame) -> pd.DataFrame:
    """
    patients.csv must have columns: patient_id, payer, autopay_enrolled (bool)
    """
    required = {"patient_id", "payer", "autopay_enrolled"}
    missing = required - set(patients.columns)
    if missing:
        raise ValueError(f"patients.csv missing columns: {missing}")

    summary = patients.groupby("payer").apply(
        lambda x: pd.Series({
            "total_patients": len(x),
            "autopay_enrolled": x["autopay_enrolled"].sum(),
            "autopay_rate_pct": round(x["autopay_enrolled"].mean() * 100, 1),
        })
    ).reset_index()

    # Flag payers under 80% as needing attention
    summary["status"] = summary["autopay_rate_pct"].apply(
        lambda r: "Critical" if r < 50 else "Review" if r < 80 else "OK"
    )
    return summary


def audit_era_posting(payments: pd.DataFrame) -> pd.DataFrame:
    """
    Classifies each payer's ERA posting mode based on era_reference field presence.
    auto: era_reference populated on >90% of payments
    manual: era_reference missing on >50% of payments
    mixed: in between
    """
    if "era_reference" not in payments.columns or "payer" not in payments.columns:
        return pd.DataFrame()

    summary = payments.groupby("payer").apply(
        lambda x: pd.Series({
            "total_payments": len(x),
            "era_present": x["era_reference"].notna().sum(),
            "era_rate_pct": round(x["era_reference"].notna().mean() * 100, 1),
        })
    ).reset_index()

    summary["posting_mode"] = summary["era_rate_pct"].apply(
        lambda r: "Auto" if r >= 90 else "Manual" if r < 50 else "Mixed"
    )
    return summary


def compute_days_to_payment(claims: pd.DataFrame, payments: pd.DataFrame) -> Optional[float]:
    merged = claims.merge(payments[["claim_id", "payment_date"]], on="claim_id", how="inner")
    if "submitted_date" not in merged.columns or "payment_date" not in merged.columns:
        return None
    merged["days_to_payment"] = (merged["payment_date"] - merged["submitted_date"]).dt.days
    return round(merged["days_to_payment"].mean(), 1)


def run_tiq_audit(
    patients_path: Path,
    payments_path: Path,
    claims_path: Path,
) -> TIQAuditResult:
    patients = pd.read_csv(patients_path)
    payments = pd.read_csv(payments_path, parse_dates=["payment_date"])
    claims = pd.read_csv(claims_path, parse_dates=["submitted_date"])

    autopay = audit_autopay(patients)
    era = audit_era_posting(payments)
    avg_days = compute_days_to_payment(claims, payments)

    # Compute cash float: unpaid claims at average daily rate
    avg_daily = payments["amount_paid"].sum() / max(1, len(payments["payment_date"].dt.date.unique()))
    float_amount = avg_daily * (avg_days or 0) * 0.59  # fraction still on manual cycle

    gaps = []
    for _, row in autopay[autopay["status"] != "OK"].iterrows():
        gaps.append(f"{row['payer']}: autopay enrollment at {row['autopay_rate_pct']}% (target: 80%+)")
    for _, row in era[era["posting_mode"] == "Manual"].iterrows():
        gaps.append(f"{row['payer']}: ERA posting manual - {100 - row['era_rate_pct']:.0f}% of payments not auto-posted")

    return TIQAuditResult(
        autopay_rates=autopay,
        era_coverage=era,
        reporting_gaps=gaps,
        avg_days_to_payment=avg_days,
        float_amount=float_amount,
    )
