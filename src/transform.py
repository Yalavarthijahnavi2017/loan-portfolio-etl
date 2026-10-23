"""Transform stage.

Job: turn the raw LendingClub-style CSV into a clean, typed loan grain.

Design notes (the "why" an interviewer will ask about):
- Grain is one row per loan. The source has no loan id, so we mint a
  surrogate key at load time and keep a content hash (row_hash) for
  dedupe/lineage.
- We keep a *curated* ~28-column subset, not all 55 source columns. The
  dropped *_joint columns only exist for joint applications and are >85%
  null; carrying them would bloat the warehouse without analytical value.
- Nulls are preserved as NULL (no imputation): inventing borrower income
  figures would be data fabrication. Validation enforces null rules only
  on columns that must never be null.
- Every helper below is a pure function so it can be unit-tested without
  touching a database.
"""
from __future__ import annotations

import hashlib
from datetime import date

import pandas as pd

# Raw -> warehouse column mapping. Columns not listed here are intentionally
# excluded from the warehouse (see module docstring).
COLUMN_MAP = {
    "issue_month": "issue_date",
    "loan_amount": "loan_amount",
    "term": "term_months",
    "interest_rate": "interest_rate",
    "installment": "installment",
    "grade": "grade",
    "sub_grade": "sub_grade",
    "loan_status": "loan_status",
    "loan_purpose": "loan_purpose",
    "application_type": "application_type",
    "homeownership": "homeownership",
    "state": "state",
    "annual_income": "annual_income",
    "verified_income": "verified_income",
    "debt_to_income": "debt_to_income",
    "emp_length": "emp_length_years",
    "emp_title": "emp_title",
    "delinq_2y": "delinq_2y",
    "inquiries_last_12m": "inquiries_last_12m",
    "open_credit_lines": "open_credit_lines",
    "total_credit_lines": "total_credit_lines",
    "balance": "balance",
    "paid_total": "paid_total",
    "paid_principal": "paid_principal",
    "paid_interest": "paid_interest",
}

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_issue_month(value: str) -> date:
    """'Mar-2018' -> date(2018, 3, 1).

    The source stores only month granularity, so day=1 is the honest
    representation (documented here, not silently invented precision).
    """
    mon, year = str(value).strip().split("-")
    return date(int(year), _MONTHS[mon.strip().lower()], 1)


def clean_state(value) -> str | None:
    """Normalize US state codes; non-strings become NULL."""
    if pd.isna(value):
        return None
    return str(value).strip().upper()


def loan_to_income_ratio(loan_amount, annual_income):
    """Loan amount as a fraction of annual income; NULL-safe.

    Guards against divide-by-zero AND against missing income — both would
    otherwise produce inf/NaN rows that silently poison aggregates.
    """
    if pd.isna(loan_amount) or pd.isna(annual_income) or annual_income == 0:
        return None
    return float(loan_amount) / float(annual_income)


def row_hash(row: pd.Series) -> str:
    """Stable md5 over the raw row's stringified values.

    Why: the source has no loan id, so this is our natural dedupe key in
    validation and a lineage fingerprint in the warehouse.
    """
    payload = "|".join("" if pd.isna(v) else str(v) for v in row.values)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def transform(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in COLUMN_MAP if c not in df.columns]
    if missing:
        raise ValueError(f"Raw data is missing expected columns: {missing}")

    out = pd.DataFrame()
    for raw_col, wh_col in COLUMN_MAP.items():
        out[wh_col] = df[raw_col]

    # --- typing & cleaning ---
    out["issue_date"] = out["issue_date"].map(parse_issue_month)
    out["state"] = out["state"].map(clean_state)
    out["homeownership"] = out["homeownership"].map(
        lambda v: None if pd.isna(v) else str(v).strip().upper()
    )
    out["loan_status"] = out["loan_status"].map(
        lambda v: None if pd.isna(v) else str(v).strip()
    )
    out["term_months"] = pd.to_numeric(out["term_months"], errors="coerce").astype("Int64")
    out["emp_length_years"] = pd.to_numeric(out["emp_length_years"], errors="coerce").astype("Int64")
    for col in ("delinq_2y", "inquiries_last_12m", "open_credit_lines", "total_credit_lines"):
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

    # --- derived fields ---
    out["loan_to_income_ratio"] = [
        loan_to_income_ratio(a, i)
        for a, i in zip(out["loan_amount"], out["annual_income"])
    ]

    # --- lineage ---
    out["row_hash"] = df.apply(row_hash, axis=1)

    return out
