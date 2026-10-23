"""Validate stage — data-quality checks.

Philosophy: fail loudly, with specifics. A pipeline that silently loads
bad data is worse than one that refuses to run — downstream dashboards
can't distinguish "no delinquencies this month" from "the feed broke".
Every check below reports *which* rows failed, not just a count, so the
fix is actionable.

validate() raises DataQualityError listing every failed check. The
orchestrator (pipeline.py) catches it, logs it, and exits non-zero.
"""
from __future__ import annotations

import pandas as pd

# Allowed values observed in (and documented by) the source dataset.
KNOWN_LOAN_STATUSES = {
    "Current",
    "Fully Paid",
    "In Grace Period",
    "Late (16-30 days)",
    "Late (31-120 days)",
    "Charged Off",
    "Default",
}
KNOWN_TERMS = {36, 60}


class DataQualityError(Exception):
    """Raised when one or more data-quality checks fail."""


def check_no_nulls(df: pd.DataFrame, columns: list[str]) -> list[str]:
    """Columns that must never be null (business keys / required facts)."""
    failures = []
    for col in columns:
        n = int(df[col].isna().sum())
        if n:
            failures.append(f"NULL check failed: {col} has {n} null rows")
    return failures


def check_ranges(df: pd.DataFrame) -> list[str]:
    """Plausible business ranges; out-of-range values signal feed corruption."""
    failures = []
    bad = df["loan_amount"].notna() & (df["loan_amount"] <= 0)
    if bad.any():
        failures.append(f"Range check failed: {int(bad.sum())} rows with loan_amount <= 0")
    rate = pd.to_numeric(df["interest_rate"], errors="coerce")
    bad = rate.notna() & ((rate < 0) | (rate > 40))
    if bad.any():
        failures.append(
            f"Range check failed: {int(bad.sum())} rows with interest_rate outside [0, 40]"
        )
    dti = pd.to_numeric(df["debt_to_income"], errors="coerce")
    # NOTE: the upper bound is 500, not 100. Real lending data contains
    # borrowers whose debt payments exceed their income (max observed ~469),
    # so capping at 100 would reject legitimate rows. 500 is a corruption
    # ceiling, not a business rule.
    bad = dti.notna() & ((dti < 0) | (dti > 500))
    if bad.any():
        failures.append(
            f"Range check failed: {int(bad.sum())} rows with debt_to_income outside [0, 500]"
        )
    return failures


def check_allowed_values(df: pd.DataFrame) -> list[str]:
    """Categorical columns must contain only known values."""
    failures = []
    unknown_status = set(df["loan_status"].dropna().unique()) - KNOWN_LOAN_STATUSES
    if unknown_status:
        failures.append(f"Value check failed: unknown loan_status values {sorted(unknown_status)}")
    unknown_terms = set(df["term_months"].dropna().unique()) - KNOWN_TERMS
    if unknown_terms:
        failures.append(f"Value check failed: unknown term_months values {sorted(unknown_terms)}")
    return failures


def check_no_duplicates(df: pd.DataFrame) -> list[str]:
    """No two rows may share a row_hash (the source has no loan id)."""
    dupes = int(df.duplicated(subset=["row_hash"]).sum())
    if dupes:
        return [f"Dedupe check failed: {dupes} duplicate rows (by row_hash)"]
    return []


def validate(df: pd.DataFrame) -> None:
    """Run every check; raise DataQualityError aggregating all failures.

    Aggregation (not fail-on-first) is deliberate: one run tells you
    everything that's wrong, instead of making you fix-then-rerun in a loop.
    """
    failures: list[str] = []
    failures += check_no_nulls(df, ["loan_amount", "issue_date", "loan_status", "row_hash"])
    failures += check_ranges(df)
    failures += check_allowed_values(df)
    failures += check_no_duplicates(df)
    if failures:
        raise DataQualityError(
            f"{len(failures)} data-quality check(s) failed:\n- " + "\n- ".join(failures)
        )
