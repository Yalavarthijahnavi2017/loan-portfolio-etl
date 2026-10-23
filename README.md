# loan-portfolio-etl

An end-to-end ETL pipeline that ingests public loan data, cleans and validates
it, and loads it into a warehouse table ready for portfolio analytics.

Built as a portfolio project demonstrating production-style data engineering:
typed transforms, fail-loud data-quality checks, unit tests, and a backend
that runs on SQLite (zero setup) or Postgres (production target) with no code
changes. On top of the warehouse sit two more layers: a **dbt project**
(staging + marts + schema tests, on DuckDB) and an **Apache Airflow DAG**
that orchestrates the unit tests, the pipeline, and the dbt build.

## What it does

```
┌────────────┐   ┌────────────┐   ┌────────────┐   ┌──────────────────┐
│  EXTRACT   │──▶│ TRANSFORM  │──▶│  VALIDATE  │──▶│       LOAD       │
│            │   │            │   │            │   │                  │
│ public CSV │   │ parse dates│   │ null rules │   │  warehouse table │
│ 10k loans  │   │ type casts │   │ range rules│   │  `loans`          │
│ 55 columns │   │ curated    │   │ allowed    │   │  full refresh      │
│            │   │ 28 columns │   │ values     │   │                  │
│            │   │ derive KPIs│   │ dedupe     │   │                  │
└────────────┘   └────────────┘   └────────────┘   └──────────────────┘
      src/extract.py  src/transform.py  src/validate.py   src/load.py
```

`pipeline.py` orchestrates the four stages with per-stage timing and logging.
Validation failures abort the run with a non-zero exit code and a report of
exactly which checks failed — bad data never silently reaches the warehouse.

The warehouse then feeds the analytics layers:

```
  warehouse.loans ──▶ dbt staging (stg_loans) ──▶ dbt marts ──▶ dashboards / analysis
   (SQLite, from        (view: real DATE types,    mart_portfolio_by_status_grade
    the ETL above)       issue_month derived)       mart_monthly_originations

  Airflow DAG `loan_portfolio_etl` (@daily):
    run_unit_tests ──▶ run_etl_pipeline ──▶ dbt_build
```

## The dataset

**Source:** OpenIntro `loans_full_schema.csv` (10,000 loans × 55 columns),
a curated public sample derived from LendingClub's published loan data.

- Download page: <https://www.openintro.org/data/index.php?data=loans_full_schema>
- Direct file: <https://www.openintro.org/data/csv/loans_full_schema.csv>
- Original publisher: LendingClub (<https://www.lendingclub.com/info/statistics.action>)

A copy is bundled at `data/raw/loans.csv` so the pipeline runs offline and
reproducibly. Run with `--refresh` to re-download from the source URL.
No real customer or employer data is used anywhere in this project.

## Warehouse model

One row per loan (`schema.sql`). Highlights:

| column | meaning |
|---|---|
| `loan_key` | surrogate PK (source has no loan id) |
| `issue_date` | loan issue month, as a DATE |
| `loan_amount`, `interest_rate`, `term_months`, `installment` | core loan terms |
| `grade`, `sub_grade`, `loan_status`, `loan_purpose` | risk / product attributes |
| `annual_income`, `debt_to_income`, `emp_length_years` | borrower profile (nulls kept as NULL — never imputed) |
| `balance`, `paid_total`, `paid_principal`, `paid_interest` | performance to date |
| `loan_to_income_ratio` | derived: `loan_amount / annual_income` (NULL-safe) |
| `row_hash` | md5 of the raw row — dedupe key + lineage fingerprint |
| `loaded_at` | load timestamp |

Joint-application columns (`*_joint`) were intentionally excluded: they are
>85% null and describe a different grain.

## dbt layer (analytics modeling)

The `dbt/` folder is a dbt project (dbt-core + the DuckDB adapter) that
models the warehouse table the ETL loads. Design choices worth knowing:

- **Source = the loaded warehouse, attached — not a copy.** `profiles.yml`
  uses dbt-duckdb's `attach:` to mount the SQLite warehouse file
  (`data/warehouse/loans.db`) inside DuckDB as the `warehouse` database.
  dbt therefore models the exact table `pipeline.py` produced; there is no
  export step that could drift out of sync.
- **Why DuckDB:** there is no Postgres server in the dev environment, and
  DuckDB is an embedded analytics engine that can read the SQLite file
  directly. (Layer 1's Postgres backend remains the production target for
  the ETL itself.)
- **Models.** `stg_loans` (view) mirrors the warehouse 1:1 but casts
  `issue_date`/`loaded_at` from SQLite's ISO text to real DATE/TIMESTAMP
  types and derives `issue_month`. Two marts (tables):
  `mart_portfolio_by_status_grade` — loan counts, amounts, average rates,
  balances and paid totals per (loan_status, grade), 37 rows on the
  bundled sample; and `mart_monthly_originations` — origination volume
  and average pricing per issue month (3 months in the bundled sample).
- **Tests.** 18 dbt data tests run with the models in a single
  `dbt build`: schema tests (`unique`/`not_null` on keys,
  `accepted_values` for loan_status/grade/term — mirroring the allowed
  values in `src/validate.py`) plus two singular tests in `dbt/tests/`:
  composite-grain uniqueness for the status×grade mart, and a
  reconciliation test proving both marts' loan totals equal the staging
  count exactly. Verified result: `Done. PASS=21` (3 models + 18 tests).

```bash
pip install -r requirements-dbt.txt
cd dbt
../.venv/bin/dbt build --profiles-dir .   # run from dbt/: profile paths are relative to it
```

First run on a fresh machine, DuckDB automatically downloads its
`sqlite_scanner` extension once (needs internet) — that is how it reads
the attached SQLite file. Note the staging view references the attached
warehouse, so ad-hoc queries against `loans_dbt.duckdb` need the same
`ATTACH` first; dbt handles it via the profile.

## Airflow orchestration

`dags/loan_etl_dag.py` defines DAG `loan_portfolio_etl` (`@daily`,
catchup off, 2 retries with a 5-minute delay). Its BashOperator tasks call
the project venv's own binaries, in dependency order:

```
run_unit_tests ──▶ run_etl_pipeline ──▶ dbt_build
   (pytest)          (pipeline.py)        (dbt build)
```

Tests gate the run: broken transform/validate code fails the first task
and the warehouse is never touched with bad logic downstream.

Validated with Apache Airflow 3.3.2: the DAG parses with zero import
errors (DagBag), and a full `airflow dags test loan_portfolio_etl` run
executed all three tasks successfully (DagRun state: success). Scope
note, stated plainly: that is a one-off test execution against a
throwaway Airflow home — the DAG has not been run under a long-lived
scheduler deployment.

To run it under a real scheduler:

```bash
pip install -r requirements-airflow.txt
export AIRFLOW__CORE__DAGS_FOLDER="$PWD/dags"
airflow db migrate
airflow scheduler   # plus `airflow api-server` for the UI, in Airflow 3
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional; defaults run on SQLite

# Optional layers
pip install -r requirements-dbt.txt      # dbt project (DuckDB engine)
pip install -r requirements-airflow.txt  # Airflow orchestration
```

Requirements: Python 3.10+. Postgres extras only needed for `DB_BACKEND=postgres`
(then create the database and set `POSTGRES_*` in `.env`).

## How to run

```bash
# Full pipeline on SQLite (default, zero setup)
python pipeline.py

# Re-download the source CSV instead of using the bundled copy
python pipeline.py --refresh

# Target Postgres instead of SQLite
python pipeline.py --backend postgres   # needs POSTGRES_* in .env

# Unit tests
pytest tests/ -v

# dbt layer: build staging + marts and run all dbt tests
cd dbt && ../.venv/bin/dbt build --profiles-dir . && cd ..

# Airflow: parse-check the DAG (zero import errors expected)
python -c "from airflow.models import DagBag; print(DagBag(dag_folder='dags/loan_etl_dag.py').import_errors)"
```

## Sample output

```
21:56:20 INFO  pipeline: Starting pipeline (backend=sqlite)
21:56:20 INFO  src.extract: Extracted 10000 rows x 55 columns
21:56:20 INFO  pipeline: Stage 'extract' finished in 0.09s
21:56:20 INFO  pipeline: Stage 'transform' finished in 0.53s
21:56:20 INFO  pipeline: Stage 'validate' finished in 0.01s
21:56:20 INFO  pipeline: Validation passed: 10000 rows clean
21:56:20 INFO  src.load: Loaded 10000 rows into loans
21:56:20 INFO  pipeline: Pipeline complete: 10000 rows loaded into 'sqlite'
```

And the warehouse answers portfolio questions immediately:

```sql
SELECT loan_status, COUNT(*),
       ROUND(AVG(interest_rate), 2) AS avg_rate,
       ROUND(AVG(loan_amount), 0)   AS avg_loan
FROM loans GROUP BY loan_status ORDER BY 2 DESC;
```

| loan_status | count | avg_rate | avg_loan |
|---|---|---|---|
| Current | 9375 | 12.31 | 16366 |
| Fully Paid | 447 | 13.41 | 15591 |
| In Grace Period | 67 | 15.64 | 18615 |
| Late (31-120 days) | 66 | 16.53 | 18840 |
| Late (16-30 days) | 38 | 16.85 | 16726 |
| Charged Off | 7 | 12.38 | 12643 |

## Project layout

```
pipeline.py              orchestrator for the core ETL
schema.sql               warehouse DDL (rendered per backend by src/load.py)
src/                     extract / transform / validate / load / config / db
tests/                   pytest unit tests for transform + validate
dbt/                     dbt project: sources, staging, marts, schema tests
  models/staging/          stg_loans (view over the attached warehouse)
  models/marts/            mart_portfolio_by_status_grade, mart_monthly_originations
  tests/                   singular tests (grain uniqueness, reconciliation)
  profiles.yml             DuckDB profile; attaches the SQLite warehouse
dags/                    Airflow DAG (loan_etl_dag.py)
data/raw/                bundled source CSV (pinned input)
data/warehouse/          SQLite warehouse file (created by the load stage)
requirements.txt         core ETL dependencies
requirements-dbt.txt     dbt layer dependencies
requirements-airflow.txt Airflow dependencies
```

## Design decisions (for the curious reviewer)

- **Fail-loud validation.** Checks aggregate all failures per run instead of
  failing on the first, so one run tells you everything wrong. Real example
  from development: the first run flagged 33 rows with `debt_to_income > 100`.
  Investigation showed DTI > 100% is legitimate in lending data (max ~469),
  so the check was corrected to `[0, 500]` with a comment — not silently
  dropped.
- **Full-refresh loads.** The source is a static snapshot with no watermark
  column, so incremental/CDC loading would be dishonest. Each run rebuilds
  the table: simple, idempotent, correct for this data shape.
- **One schema file, two backends.** `schema.sql` uses `{PK}` / `{NOW}`
  placeholders rendered per backend — a single source of truth instead of
  two drift-prone DDL files.
- **No imputation.** Missing borrower fields stay NULL. Inventing income
  figures would be data fabrication.
- **dbt models the loaded warehouse, not the raw file.** The pipeline's
  validate stage is the data-quality gate for ingestion; dbt starts from
  data that already passed it and adds *declarative* checks (schema tests)
  at the modeling layer, where a broken mart fails the build instead of
  quietly feeding a dashboard. The two test layers check different
  things on purpose: pytest tests code, dbt tests data.
- **The DAG runs the project's venv, not Airflow's.** Each BashOperator
  invokes `.venv/bin/...` binaries so the orchestrated steps use the
  project's pinned dependencies — the same versions a developer runs
  locally — instead of whatever the Airflow environment happens to have.
