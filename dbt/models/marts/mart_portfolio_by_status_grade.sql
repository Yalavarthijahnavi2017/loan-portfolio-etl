-- Mart: portfolio composition and performance by loan status x grade.
-- Grain: one row per (loan_status, grade) combination present in staging.
-- This is the dbt twin of the README's sample SQL query, extended with
-- grade and money totals so it can drive a portfolio dashboard.

select
    loan_status,
    grade,
    count(*) as loan_count,
    sum(loan_amount) as total_loan_amount,
    round(avg(loan_amount), 2) as avg_loan_amount,
    round(avg(interest_rate), 2) as avg_interest_rate,
    round(avg(loan_to_income_ratio), 4) as avg_loan_to_income_ratio,
    sum(balance) as total_balance,
    sum(paid_total) as total_paid_to_date,
    round(100.0 * count(*) / sum(count(*)) over (), 2) as pct_of_loans

from {{ ref('stg_loans') }}

group by loan_status, grade
