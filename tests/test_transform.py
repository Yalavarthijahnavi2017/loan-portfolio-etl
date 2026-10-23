"""Unit tests for src/transform.py.

These test the pure helper functions and the transform() contract with
small hand-built frames — no database, no network, no fixture files.
Run: pytest tests/ -v
"""
from datetime import date

import pandas as pd
import pytest

from src.transform import (
    COLUMN_MAP,
    clean_state,
    loan_to_income_ratio,
    parse_issue_month,
    row_hash,
    transform,
)


def make_raw_row(**overrides):
    """One valid raw row; override any column to simulate edge cases."""
    row = {
        "issue_month": "Mar-2018",
        "loan_amount": 10000.0,
        "term": 36,
        "interest_rate": 12.5,
        "installment": 333.33,
        "grade": "B",
        "sub_grade": "B3",
        "loan_status": "Current",
        "loan_purpose": "debt_consolidation",
        "application_type": "individual",
        "homeownership": "RENT",
        "state": "ca",
        "annual_income": 60000.0,
        "verified_income": "Verified",
        "debt_to_income": 15.0,
        "emp_length": 5.0,
        "emp_title": "analyst",
        "delinq_2y": 0,
        "inquiries_last_12m": 2,
        "open_credit_lines": 8,
        "total_credit_lines": 12,
        "balance": 8000.0,
        "paid_total": 2500.0,
        "paid_principal": 2000.0,
        "paid_interest": 500.0,
    }
    row.update(overrides)
    return row


def make_raw_df(n=3, **overrides):
    # Vary loan_amount per row so identical-row fixtures don't trip the
    # duplicate check in validate() tests.
    frames = []
    for i in range(n):
        row = make_raw_row(**overrides)
        row["loan_amount"] = row["loan_amount"] + i * 137.0
        frames.append(row)
    return pd.DataFrame(frames)


def test_parse_issue_month():
    assert parse_issue_month("Mar-2018") == date(2018, 3, 1)
    assert parse_issue_month("jan-2020") == date(2020, 1, 1)
    assert parse_issue_month("Dec-2015") == date(2015, 12, 1)


def test_clean_state():
    assert clean_state("ca") == "CA"
    assert clean_state(" NY ") == "NY"
    assert clean_state(None) is None
    assert clean_state(float("nan")) is None


def test_loan_to_income_ratio():
    assert loan_to_income_ratio(10000.0, 50000.0) == pytest.approx(0.2)
    assert loan_to_income_ratio(10000.0, 0) is None  # divide-by-zero guard
    assert loan_to_income_ratio(10000.0, None) is None
    assert loan_to_income_ratio(None, 50000.0) is None


def test_row_hash_stable_and_sensitive():
    row = pd.Series({"a": 1, "b": "x"})
    assert row_hash(row) == row_hash(row)  # deterministic
    assert row_hash(row) != row_hash(pd.Series({"a": 1, "b": "y"}))


def test_transform_selects_curated_columns():
    df = transform(make_raw_df())
    expected = set(COLUMN_MAP.values()) | {"loan_to_income_ratio", "row_hash"}
    assert set(df.columns) == expected


def test_transform_types_and_values():
    df = transform(make_raw_df(n=1))
    r = df.iloc[0]
    assert r["issue_date"] == date(2018, 3, 1)
    assert r["state"] == "CA"
    assert r["homeownership"] == "RENT"
    assert r["loan_to_income_ratio"] == pytest.approx(10000.0 / 60000.0)
    assert isinstance(r["row_hash"], str) and len(r["row_hash"]) == 32


def test_transform_preserves_nulls():
    df = transform(make_raw_df(n=1, emp_length=float("nan"), debt_to_income=float("nan")))
    assert pd.isna(df.iloc[0]["emp_length_years"])
    assert pd.isna(df.iloc[0]["debt_to_income"])


def test_transform_rejects_missing_columns():
    with pytest.raises(ValueError, match="missing expected columns"):
        transform(pd.DataFrame({"wrong": [1]}))
