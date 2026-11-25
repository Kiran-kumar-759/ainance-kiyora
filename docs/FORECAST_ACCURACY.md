# Forecast Accuracy & Time-Aware Backtesting (Phase 9)

Implemented in `backend/app/services/forecasting/forecast_evaluation.py` and exposed via `GET /api/v1/forecasting/accuracy` & `GET /api/v1/forecasting/evaluation/history`.

## Zero Future Data Leakage Protocol
1. For an evaluation window (`14`–`90` days, default `30d`), splits history strictly at `cutoff_date = as_of_date - eval_window`.
2. Passes ONLY transactions dated `<= cutoff_date` into `forecast_expenses`, `forecast_income`, and `forecast_categories` (never peeking at outcomes after `cutoff_date`).
3. Compares predicted expenses, income, net cash flow, and category totals against realized transactions strictly inside `(cutoff_date, as_of_date]`.

## Reported Metrics (Decimal Precision)
- **MAE:** Mean Absolute Error across evaluated categories (`SUM(|pred_c - actual_c|) / N`).
- **RMSE:** Root Mean Squared Error across categories.
- **WAPE %:** Weighted Absolute Percentage Error (`|pred_exp - actual_exp| / actual_exp * 100`), omitted (`null`) if `actual_exp == 0` instead of dividing by zero (no fragile MAPE).
- **Bias:** Signed error (`predicted_expense - actual_expense`).

If pre-cutoff history spans `< 28` days or `< 4` expenses, returns `status = "insufficient_history"` transparently.
