# Statistical Anomaly Detection (Phase 8)

Implemented in `backend/app/services/ai/anomaly_service.py`.

## Methodology
- Uses robust non-parametric statistics (**Median + MAD** — Median Absolute Deviation) rather than fragile means on skewed personal spending data, with practical minimum ₹ thresholds to eliminate micro-noise alerts:
  1. `category_transaction_spike` (`robust_median_mad`): Single expense >= ₹500 above category median with modified Z-score >= 3.5 and >= 2.0x median (minimum 4 historical samples in category).
  2. `category_monthly_spike` (`monthly_baseline_comparison`): Latest month category total >= 1.65x prior monthly median (+>= ₹1,000, minimum 3 months).
  3. `recurring_amount_jump` (`recurring_charge_delta`): Latest recurring merchant charge >= 1.20x prior median (+>= ₹100).
- **Responsible Framing:** Anomalies never carry `"fraud"` claims; they surface statistical baseline deviations and supporting transaction IDs for user `acknowledge`, `dismiss`, or `reopen`.
- **Deduplication:** Controlled by unique `(user_id, dedupe_key)` preserving prior user review state across re-runs.
