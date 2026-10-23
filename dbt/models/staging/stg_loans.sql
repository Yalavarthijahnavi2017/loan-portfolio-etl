-- Staging: 1:1 with the ETL warehouse table, with warehouse-safe types.
--
-- The ETL stores issue_date / loaded_at as ISO text in SQLite (SQLite has
-- no native DATE type), so the casts here are real work, not ceremony:
-- downstream models can rely on issue_date being a DATE and on
-- issue_month being the first of the loan's origination month.
-- No filtering, no aggregation — staging must not silently change the
-- grain or drop rows the ETL validated.

with source as (

    select * from {{ source('warehouse', 'loans') }}

),

staged as (

    select
        loan_key,
        cast(issue_date as date) as issue_date,
        cast(date_trunc('month', cast(issue_date as date)) as date) as issue_month,
        loan_amount,
        term_months,
        interest_rate,
        installment,
        grade,
        sub_grade,
        loan_status,
        loan_purpose,
        application_type,
        homeownership,
        state,
        annual_income,
        verified_income,
        debt_to_income,
        emp_length_years,
        emp_title,
        delinq_2y,
        inquiries_last_12m,
        open_credit_lines,
        total_credit_lines,
        balance,
        paid_total,
        paid_principal,
        paid_interest,
        loan_to_income_ratio,
        row_hash,
        cast(loaded_at as timestamp) as loaded_at

    from source

)

select * from staged
