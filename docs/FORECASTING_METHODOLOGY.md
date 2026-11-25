# Forecasting Methodology, Confidence & Known Limitations (Phase 9)

## Supported Horizons & Method Selection
- Supported horizons: **7 days**, **30 days**, **90 days**, **180 days (6 months)**, and **365 days (12 months)** resolved relative to the user's configured timezone (`UserPreference.timezone`, defaulting to `Asia/Kolkata`).
- **Expenses (`expense_income_forecaster.py`):**
  1. Separates historical discretionary spending from scheduled payment sources (`bill_payment`, `subscription_payment`, `loan_payment` and active commitment names) so confirmed upcoming obligations (`commitment_forecaster.py`) are added cleanly **without double-counting**.
  2. Uses linearly weighted monthly moving averages + bounded (`±35%`) dampened recent trends + day-of-week indices (`[0.50, 1.80]`) when `>= 14` observations exist; falls back to rolling daily averages for shorter histories (`>= 14` days) or confirmed-commitments-only when historical spend is insufficient.
- **Income:** Classifies income into `regular_monthly`, `multi_source_regular`, `irregular`, or `insufficient_data` using distinct month counts and CV (`stdev / mean`), excluding loan disbursements and internal transfers.

## Empirical Confidence & Bounds
`assess_forecast_confidence()` scores:
- Observation count (`< 3` -> `insufficient_data`)
- Historical span in days (`< 14` without schedules -> `insufficient_data`, `>= 180` max contribution)
- Spending stability via coefficient of variation across months
- Presence of confirmed upcoming obligations
- Horizon decay penalty (`90d`, `180d`, `365d`)

Outputs `high` (`>= 0.72`), `medium` (`>= 0.48`), `low`, or `insufficient_data`, plus `[lower_bound, upper_bound]` derived from empirical historical volatility rather than hardcoded percentages.
