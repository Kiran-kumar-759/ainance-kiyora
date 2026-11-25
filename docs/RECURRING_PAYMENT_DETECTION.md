# Recurring Payment Detection & Phase 6 Integration (Phase 8)

Implemented in `backend/app/services/ai/recurring_intelligence.py`.

## Detection Logic
- Groups active non-transfer expense transactions by normalized `merchant_key`.
- Classifies cadence windows across `weekly` (5–9d), `monthly` (24–37d), `quarterly` (78–105d), `half_yearly` (165–198d), and `yearly` (340–390d).
- Supports both fixed-price commitments (`Netflix`, `Rent`, `EMI`) and variable-amount recurring utilities (`BESCOM Electricity`, `Broadband`, where `amount_variability_pct > 10%` marks `is_variable_amount = true`).
- Cross-references existing Phase 6 `subscriptions` so already-tracked commitments link automatically without duplicate prompts.
- On `POST /api/v1/intelligence/recurring-candidates/{id}/decision`, users can `confirm`, `reject`, link to an existing subscription, or create a new Phase 6 `Subscription` explicitly.
