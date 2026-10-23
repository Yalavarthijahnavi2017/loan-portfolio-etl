-- Singular test: the mart grain (loan_status, grade) must be unique.
-- dbt's built-in `unique` test only covers single columns, so the
-- composite-grain check lives here. Returns rows only on failure.

select
    loan_status,
    grade,
    count(*) as rows_per_grain

from {{ ref('mart_portfolio_by_status_grade') }}

group by loan_status, grade
having count(*) > 1
