-- Warehouse DDL for the loans fact table.
-- Grain: one row per loan.
--
-- Portability: this file is written once and rendered per backend by src/load.py.
--   {PK}  -> "INTEGER"      on SQLite (INTEGER PRIMARY KEY aliases the rowid, auto-increments)
--         -> "SERIAL"       on Postgres (auto-incrementing integer)
--   {NOW} -> "CURRENT_TIMESTAMP" on SQLite (function calls like
--            datetime('now') are not allowed as column DEFAULTs)
--         -> "now()"           on Postgres
-- Why: keeps a single source of truth for the schema instead of two drift-prone files.

DROP TABLE IF EXISTS loans;

CREATE TABLE loans (
    loan_key        {PK} PRIMARY KEY,
    issue_date      DATE        NOT NULL,
    loan_amount     NUMERIC(12, 2) NOT NULL CHECK (loan_amount > 0),
    term_months     INTEGER     NOT NULL CHECK (term_months IN (36, 60)),
    interest_rate   NUMERIC(5, 2)  NOT NULL CHECK (interest_rate >= 0 AND interest_rate <= 40),
    installment     NUMERIC(12, 2),
    grade           VARCHAR(2),
    sub_grade       VARCHAR(3),
    loan_status     VARCHAR(30) NOT NULL,
    loan_purpose    VARCHAR(40),
    application_type VARCHAR(20),
    homeownership   VARCHAR(20),
    state           VARCHAR(2),
    annual_income   NUMERIC(14, 2),
    verified_income VARCHAR(20),
    debt_to_income  NUMERIC(6, 2),
    emp_length_years INTEGER,
    emp_title       TEXT,
    delinq_2y       INTEGER,
    inquiries_last_12m INTEGER,
    open_credit_lines  INTEGER,
    total_credit_lines INTEGER,
    balance         NUMERIC(14, 2),
    paid_total      NUMERIC(14, 2),
    paid_principal  NUMERIC(14, 2),
    paid_interest   NUMERIC(14, 2),
    loan_to_income_ratio NUMERIC(8, 4),
    row_hash        CHAR(32)    NOT NULL,
    loaded_at       TIMESTAMP   NOT NULL DEFAULT {NOW}
);

CREATE INDEX IF NOT EXISTS idx_loans_issue_date  ON loans (issue_date);
CREATE INDEX IF NOT EXISTS idx_loans_loan_status ON loans (loan_status);
CREATE INDEX IF NOT EXISTS idx_loans_grade       ON loans (grade);
