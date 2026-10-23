"""Unit tests for src/validate.py.

Strategy: build a small *valid* transformed frame, then break one rule at
a time and assert validate() raises naming that rule. This proves each
check actually fires — a test suite where every test passes on broken
validators is worthless.
"""
import pandas as pd
import pytest

from src.transform import transform
from src.validate import DataQualityError, validate
from tests.test_transform import make_raw_df


def valid_frame(n=5):
    return transform(make_raw_df(n=n))


def test_validate_passes_on_clean_data():
    validate(valid_frame())  # must not raise


def test_validate_rejects_null_loan_amount():
    df = valid_frame()
    df.loc[0, "loan_amount"] = None
    with pytest.raises(DataQualityError, match="loan_amount.*null"):
        validate(df)


def test_validate_rejects_negative_loan_amount():
    df = valid_frame()
    df.loc[0, "loan_amount"] = -500.0
    with pytest.raises(DataQualityError, match="loan_amount <= 0"):
        validate(df)


def test_validate_rejects_absurd_interest_rate():
    df = valid_frame()
    df.loc[0, "interest_rate"] = 250.0
    with pytest.raises(DataQualityError, match="interest_rate"):
        validate(df)


def test_validate_allows_high_but_real_dti():
    # DTI > 100% is legitimate in lending data (debt can exceed income),
    # so the check must not reject it.
    df = valid_frame()
    df.loc[0, "debt_to_income"] = 132.06
    validate(df)  # must not raise


def test_validate_rejects_unknown_loan_status():
    df = valid_frame()
    df.loc[0, "loan_status"] = "Mystery"
    with pytest.raises(DataQualityError, match="unknown loan_status"):
        validate(df)


def test_validate_rejects_unknown_term():
    df = valid_frame()
    df.loc[0, "term_months"] = 12
    with pytest.raises(DataQualityError, match="unknown term_months"):
        validate(df)


def test_validate_rejects_duplicates():
    df = valid_frame(n=3)
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # exact dupe row
    with pytest.raises(DataQualityError, match="duplicate"):
        validate(df)


def test_validate_reports_all_failures_at_once():
    df = valid_frame()
    df.loc[0, "loan_amount"] = -1.0
    df.loc[1, "interest_rate"] = 999.0
    with pytest.raises(DataQualityError) as exc_info:
        validate(df)
    msg = str(exc_info.value)
    assert "loan_amount" in msg and "interest_rate" in msg
