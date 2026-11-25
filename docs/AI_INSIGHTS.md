# Evidence-Backed Insights & Spending Patterns (Phase 8)

Implemented in `backend/app/services/ai/pattern_service.py` and `backend/app/services/ai/insight_service.py`.

## Deterministic Spending Patterns
Computes exact `Decimal` aggregations over active non-transfer transactions for:
- Category & Merchant totals and shares
- Monthly (`total_expense`, `total_income`, `recurring_expense`, `non_recurring_expense`), Weekly, and Day-of-Week distributions
- `essential_total` vs `discretionary_total`, `fixed_total` vs `variable_total`, `weekend_expense` vs `weekday_expense`, and Top-1 / Top-3 merchant concentration percentages.

## Insights Generation
Produces deduplicated `FinancialInsight` records grounded strictly in verified metrics (discretionary share, month-over-month surges, recurring commitment share, weekend spending skew, merchant concentration, open anomalies, and categorization review backlog). Optional Groq narrative enrichment rewrites explanations without modifying or fabricating numbers.
