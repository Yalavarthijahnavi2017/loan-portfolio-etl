"""Airflow DAG: loan_portfolio_etl.

Orchestrates the three layers of this project in dependency order:

    run_unit_tests -> run_etl_pipeline -> dbt_build

- run_unit_tests: the pytest suite for the transform/validate logic.
  Tests gate the run: if the code is broken we never touch the warehouse.
- run_etl_pipeline: pipeline.py — extract -> transform -> validate ->
  load into the SQLite warehouse (full refresh). The pipeline's own
  data-quality validation aborts the task (non-zero exit) on bad data.
- dbt_build: `dbt build` — builds the staging model and both marts and
  runs every dbt schema test + singular test in one command.

Paths are derived from this file's location, so the DAG works from any
Airflow home as long as the project (including its .venv) stays in place.
Both BashOperators call the project venv's binaries on purpose: the DAG
must run the *project's* pinned dependencies, not whatever happens to be
installed in the Airflow environment.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

try:  # Airflow 3.x moved BashOperator into the standard provider package.
    from airflow.providers.standard.operators.bash import BashOperator
except ImportError:  # Airflow 2.x
    from airflow.operators.bash import BashOperator

try:
    from airflow.sdk import DAG
except ImportError:  # Airflow 2.x
    from airflow import DAG

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_BIN = PROJECT_ROOT / ".venv" / "bin"
DBT_DIR = PROJECT_ROOT / "dbt"

default_args = {
    "owner": "jahnavi",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="loan_portfolio_etl",
    description=(
        "Unit tests, then the loan ETL pipeline (SQLite warehouse), "
        "then the dbt staging/mart build with schema tests."
    ),
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["etl", "loans", "dbt", "portfolio"],
) as dag:

    run_unit_tests = BashOperator(
        task_id="run_unit_tests",
        bash_command=(
            f"cd {PROJECT_ROOT} && {VENV_BIN}/python -m pytest tests/ -q"
        ),
    )

    run_etl_pipeline = BashOperator(
        task_id="run_etl_pipeline",
        bash_command=f"cd {PROJECT_ROOT} && {VENV_BIN}/python pipeline.py",
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"cd {DBT_DIR} && {VENV_BIN}/dbt build --profiles-dir .",
    )

    run_unit_tests >> run_etl_pipeline >> dbt_build
