# Merchant Intelligence & Normalization (Phase 8)

Implemented in `backend/app/services/ai/merchant_intelligence.py`.

## How Normalization Works
- Strips noisy Indian banking & UPI prefixes/tokens (`UPI/`, `NEFT`, `IMPS`, `RTGS`, `POS`, `UTR`, `@okaxis`/`@ybl`, long reference numbers, and dates).
- Maps known Indian and global merchants into canonical keys (`swiggy`, `amazon_prime`, `bescom`, `irctc`, etc.) and tracks unknown merchants under cleaned display names.
- Records every observed `raw_pattern` under `merchant_aliases` with `occurrence_count`, while aggregating user transaction counts and `total_spent` on `merchant_identities`.
- Users can rename canonical display names, mark merchants confirmed (`is_user_confirmed`), and set authoritative default categories (`PATCH /api/v1/intelligence/merchants/{merchant_id}`), which immediately apply to future categorizations and optional unconfirmed suggestions.
