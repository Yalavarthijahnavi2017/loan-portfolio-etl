-- Singular test (reconciliation): the marts must account for every
-- staged loan exactly once. If either total drifts from staging, a join
-- or filter somewhere is silently dropping or duplicating loans.
-- Returns rows only on failure.

with staging_total as (

    select count(*) as n from {{ ref('stg_loans') }}

),

status_grade_total as (

    select sum(loan_count) as n from {{ ref('mart_portfolio_by_status_grade') }}

),

monthly_total as (

    select sum(loans_issued) as n from {{ ref('mart_monthly_originations') }}

)

select
    staging_total.n as staging_loans,
    status_grade_total.n as status_grade_loans,
    monthly_total.n as monthly_loans

from staging_total, status_grade_total, monthly_total

where staging_total.n <> status_grade_total.n
   or staging_total.n <> monthly_total.n
