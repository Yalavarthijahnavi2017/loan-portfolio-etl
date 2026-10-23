-- Mart: origination volume and pricing trends by issue month.
-- Grain: one row per issue_month.

select
    issue_month,
    count(*) as loans_issued,
    sum(loan_amount) as total_loan_amount,
    round(avg(loan_amount), 2) as avg_loan_amount,
    round(avg(interest_rate), 2) as avg_interest_rate,
    round(avg(installment), 2) as avg_installment,
    round(avg(annual_income), 2) as avg_annual_income,
    round(avg(debt_to_income), 2) as avg_debt_to_income

from {{ ref('stg_loans') }}

group by issue_month
