# Mental Health Revenue Cycle Audit Toolkit

A Python toolkit for auditing revenue cycle management in private mental health practices. Identifies claims leakage, billing workflow gaps, and TIQ reconciliation issues.

## What It Does

- Reconciles sessions vs billed vs paid from practice management exports
- Analyzes claim denial rates by payer, CPT code, and denial reason
- Audits TIQ autopay enrollment and ERA posting coverage
- Generates a prioritized HTML/PDF report of top revenue leakage points

## Quickstart

```bash
pip install -r requirements.txt
python audit/run_audit.py --data sample_data/ --output reports/
```

## Input Format

The toolkit expects CSV exports from your practice management system (TIQ, TherapyNotes, SimplePractice, etc.):

| File | Description |
|------|-------------|
| `sessions.csv` | All completed sessions with date, provider, CPT, patient ID |
| `claims.csv` | Submitted claims with status, payer, amount billed |
| `payments.csv` | Posted payments with ERA reference, amount paid, denial codes |
| `patients.csv` | Patient insurance and autopay enrollment status |

See `sample_data/` for anonymized example files.

## Output

- `reports/leakage_report.html` - Interactive dark-theme diagnostic report
- `reports/reconciliation_matrix.xlsx` - Row-level sessions vs billed vs paid
- `reports/claims_analysis.xlsx` - Denial breakdown by payer and code
- `reports/tiq_audit.xlsx` - Autopay and ERA coverage heatmap

## Modules

```
audit/
  reconcile.py        - Session-to-payment reconciliation engine
  claims_analyzer.py  - Denial pattern analysis by payer and CPT
  tiq_parser.py       - TIQ export parser and autopay audit
  report_generator.py - HTML + Excel report builder
sample_data/
  sessions_sample.csv
  claims_sample.csv
  payments_sample.csv
```

## Author

Dr. Sandeep Grover — PhD Data Science, 10+ years clinical data analysis
