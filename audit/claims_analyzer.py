"""
Claims denial analysis by payer, CPT code, and denial reason.
Produces a ranked leakage table and payer-level denial rate breakdown.
"""

import pandas as pd
from pathlib import Path


# Standard CMS denial code descriptions
DENIAL_DESCRIPTIONS = {
    "CO-4": "Modifier missing or invalid",
    "CO-16": "Missing or incorrect information",
    "CO-50": "Non-covered / not medically necessary",
    "CO-97": "Authorization expired or missing",
    "CO-109": "Claim not covered by this payer",
    "PR-2": "Patient deductible responsibility",
    "PR-3": "Patient co-pay responsibility",
    "CO-18": "Duplicate claim or service",
    "CO-29": "Timely filing limit exceeded",
    "CO-96": "Non-covered service",
}


def analyze_denials(claims: pd.DataFrame) -> dict:
    denied = claims[claims["status"] == "denied"].copy()

    if denied.empty:
        return {"payer_rates": pd.DataFrame(), "denial_codes": pd.DataFrame(), "top_issues": []}

    # Denial rate by payer
    payer_summary = claims.groupby("payer").apply(
        lambda x: pd.Series({
            "total_claims": len(x),
            "denied": (x["status"] == "denied").sum(),
            "denial_rate_pct": round((x["status"] == "denied").mean() * 100, 1),
            "amount_at_risk": x.loc[x["status"] == "denied", "amount_billed"].sum(),
        })
    ).reset_index()

    # Denial code breakdown
    code_summary = (
        denied.groupby("denial_code")
        .agg(count=("claim_id", "count"), amount_at_risk=("amount_billed", "sum"))
        .reset_index()
        .sort_values("count", ascending=False)
    )
    code_summary["description"] = code_summary["denial_code"].map(DENIAL_DESCRIPTIONS).fillna("Other")

    # Severity classification
    high_volume_codes = code_summary[code_summary["count"] >= 10]["denial_code"].tolist()
    top_issues = []
    for _, row in code_summary.head(5).iterrows():
        severity = "Critical" if row["count"] >= 10 else "Medium" if row["count"] >= 5 else "Low"
        top_issues.append({
            "code": row["denial_code"],
            "description": row["description"],
            "count": row["count"],
            "amount_at_risk": row["amount_at_risk"],
            "severity": severity,
        })

    return {
        "payer_rates": payer_summary,
        "denial_codes": code_summary,
        "top_issues": top_issues,
    }


def analyze_cpt_leakage(claims: pd.DataFrame, sessions: pd.DataFrame) -> pd.DataFrame:
    merged = sessions.merge(claims[["session_id", "status", "denial_code", "amount_billed"]], on="session_id", how="left")
    cpt_summary = merged.groupby("cpt_code").apply(
        lambda x: pd.Series({
            "session_count": len(x),
            "denial_count": (x["status"] == "denied").sum(),
            "denial_rate_pct": round((x["status"] == "denied").mean() * 100, 1),
            "amount_at_risk": x.loc[x["status"] == "denied", "amount_billed"].sum(),
        })
    ).reset_index()
    return cpt_summary.sort_values("denial_rate_pct", ascending=False)
