# Layered Transaction Categorization & Per-User ML (Phase 8)

Implemented in `backend/app/services/ai/categorization_service.py` and `backend/app/services/ai/ml_classifier.py`.

## Decision Priority Order
1. **Explicit User Override / Confirmation:** Preserved automatically on subsequent pipeline runs (`classification_method` = `user_override` or `user_confirmed`).
2. **Authoritative Merchant Mapping:** Applied from `merchant_category_mappings` (`confirmed_mapping`, confidence `0.98`).
3. **Deterministic India-First Rules:** Matches Indian merchants (`Swiggy`, `Zomato`, `Blinkit`, `Zepto`, `BESCOM`, `IRCTC`, `LIC`, etc.) and income/expense keywords (`deterministic_rule`).
4. **Per-User Supervised Classifier (`TF-IDF + LogisticRegression`):** Evaluates predictions strictly matching `transaction_type` when trained (`>= 12` labeled samples across `>= 2` classes with `>= 2` samples per class). Reports `insufficient_data` honestly otherwise without fabricating metrics.
5. **Optional Groq Fallback:** Invoked only for ambiguous items when `GROQ_ENABLED=true`, redacted via `sanitize_text_for_ai`, validated via `GroqCategorizationSchema`, and signature-cached (`input_signature`).
6. **Needs Review / Fallback:** Low-confidence, generic (`Other Expenses`), or differing suggestions stay flagged as `needs_review` until confirmed by the user.
