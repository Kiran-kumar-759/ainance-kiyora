import datetime as dt
import hashlib
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.finance import FinancialCategory, FinancialTransaction
from app.models.intelligence import (
    MerchantCategoryMapping,
    TransactionCategorization,
)
from app.repositories.intelligence.intelligence_repository import IntelligenceRepository
from app.services.ai.ai_provider import AiProvider, CategorizationAiInput, NullAiProvider
from app.services.ai.ai_validation import sanitize_text_for_ai
from app.services.ai.merchant_intelligence import (
    NormalizedMerchantResult,
    resolve_or_upsert_merchant,
)
from app.services.ai.ml_classifier import (
    load_user_pipeline,
    predict_transaction_category,
)

# Deterministic rule table for India-first personal finance categorization
EXPENSE_KEYWORD_RULES: tuple[tuple[str, tuple[str, ...], float], ...] = (
    (
        "Food & Dining",
        (
            "swiggy",
            "zomato",
            "restaurant",
            "cafe",
            "coffee",
            "bakery",
            "biryani",
            "pizza",
            "burger",
            "hotel",
            "dining",
            "eatery",
            "tea",
            "canteen",
        ),
        0.91,
    ),
    (
        "Groceries",
        (
            "blinkit",
            "zepto",
            "bigbasket",
            "instamart",
            "dmart",
            "supermarket",
            "kirana",
            "grocery",
            "groceries",
            "vegetables",
            "fruits",
            "milk",
            "dairy",
            "country delight",
            "reliance fresh",
            "jiomart",
        ),
        0.91,
    ),
    (
        "Subscriptions",
        (
            "netflix",
            "prime video",
            "amazon prime",
            "hotstar",
            "jiohotstar",
            "spotify",
            "youtube premium",
            "sonyliv",
            "zee5",
            "icloud",
            "google one",
            "chatgpt",
            "openai",
            "subscription",
            "membership",
        ),
        0.93,
    ),
    (
        "Transportation",
        (
            "uber",
            "ola",
            "rapido",
            "metro",
            "petrol",
            "diesel",
            "fuel",
            "indianoil",
            "iocl",
            "bpcl",
            "hpcl",
            "fastag",
            "toll",
            "parking",
            "cab",
            "auto",
        ),
        0.90,
    ),
    (
        "Utilities & Bills",
        (
            "electricity",
            "bescom",
            "tata power",
            "adani electricity",
            "water bill",
            "broadband",
            "fibernet",
            "wifi",
            "internet",
            "airtel",
            "jio",
            "vodafone",
            "postpaid",
            "prepaid",
            "recharge",
            "gas bill",
            "lpg",
            "mahanagar gas",
            "indane",
            "utility",
        ),
        0.90,
    ),
    (
        "Housing & Rent",
        ("rent", "landlord", "house rent", "maintenance society", "nobroker", "mygate", "pg rent", "hostel"),
        0.91,
    ),
    (
        "Healthcare",
        (
            "pharmacy",
            "medical",
            "hospital",
            "clinic",
            "doctor",
            "apollo",
            "pharmeasy",
            "1mg",
            "practo",
            "medplus",
            "diagnostic",
            "lab test",
            "dental",
            "medicine",
        ),
        0.91,
    ),
    (
        "Education",
        ("tuition", "school", "college", "university", "udemy", "coursera", "exam fee", "books", "stationery"),
        0.88,
    ),
    (
        "Entertainment",
        ("bookmyshow", "cinema", "movie", "pvr", "inox", "concert", "gaming", "playstation", "steam"),
        0.88,
    ),
    (
        "Travel",
        ("irctc", "flight", "airline", "indigo", "air india", "vistara", "makemytrip", "goibibo", "redbus", "train", "resort"),
        0.90,
    ),
    (
        "Insurance",
        ("insurance", "lic", "policy premium", "term plan", "health cover", "hdfc ergo", "icici lombard", "acko", "digit"),
        0.91,
    ),
    (
        "Loan Interest",
        ("emi", "loan interest", "bajaj finserv", "home loan", "car loan", "personal loan", "interest debit"),
        0.89,
    ),
    (
        "Shopping",
        ("amazon", "flipkart", "myntra", "ajio", "nykaa", "meesho", "croma", "decathlon", "apparel", "electronics", "mall"),
        0.86,
    ),
)

INCOME_KEYWORD_RULES: tuple[tuple[str, tuple[str, ...], float], ...] = (
    ("Salary", ("salary", "payroll", "stipend", "wages", "monthly pay", "sal cr"), 0.94),
    ("Freelance", ("freelance", "consulting", "retainer", "invoice payment", "client payout"), 0.89),
    ("Business", ("business revenue", "merchant settlement", "sales proceeds", "razorpay payout", "stripe payout"), 0.88),
    ("Investments / Interest", ("dividend", "interest credit", "int cr", "fd interest", "mutual fund", "yield"), 0.90),
    ("Cashback & Rewards", ("cashback", "reward", "refund", "reversal", "promo credit"), 0.88),
)


@dataclass
class CategorizationOutcome:
    processed: int = 0
    needs_review: int = 0
    auto_categorized: int = 0
    rule_matched: int = 0
    ml_matched: int = 0
    llm_matched: int = 0
    user_preserved: int = 0
    llm_calls: int = 0


def _tx_signature(tx: FinancialTransaction, use_ai_fallback: bool, model_version: str | None) -> str:
    raw = "|".join(
        [
            str(tx.id),
            tx.transaction_type,
            str(tx.amount),
            (tx.description or "").strip().lower(),
            (tx.merchant_payee or "").strip().lower(),
            str(tx.category_id or ""),
            str(use_ai_fallback),
            model_version or "",
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _amount_band_label(amount: Decimal) -> str:
    val = float(amount or Decimal("0"))
    if val < 200:
        return "under INR 200"
    if val < 1000:
        return "INR 200 - 1,000"
    if val < 5000:
        return "INR 1,000 - 5,000"
    if val < 25000:
        return "INR 5,000 - 25,000"
    return "above INR 25,000"


def _match_deterministic_rule(
    tx: FinancialTransaction,
    parsed_merchant: NormalizedMerchantResult,
    categories_by_name: dict[str, FinancialCategory],
) -> tuple[FinancialCategory | None, float, str | None, list[str]]:
    # First check canonical merchant default category if expense
    if tx.transaction_type == "expense" and parsed_merchant.known_default_category:
        cat = categories_by_name.get(parsed_merchant.known_default_category.lower())
        if cat:
            return (
                cat,
                0.92,
                f"Matched known Indian merchant '{parsed_merchant.normalized_name}' to '{cat.name}'.",
                [f"canonical_merchant:{parsed_merchant.canonical_key}"],
            )

    haystack = " ".join(
        [
            (tx.merchant_payee or ""),
            (tx.description or ""),
            parsed_merchant.normalized_name,
        ]
    ).lower()

    rules = EXPENSE_KEYWORD_RULES if tx.transaction_type == "expense" else INCOME_KEYWORD_RULES
    for cat_name, keywords, base_conf in rules:
        matched_kws = [kw for kw in keywords if kw in haystack]
        if matched_kws:
            cat = categories_by_name.get(cat_name.lower())
            if cat:
                return (
                    cat,
                    base_conf,
                    f"Matched deterministic rule keywords ({', '.join(matched_kws[:3])}) -> '{cat.name}'.",
                    [f"keyword:{kw}" for kw in matched_kws[:4]],
                )
    return None, 0.0, None, []


def run_categorization_for_user(
    db: Session,
    repo: IntelligenceRepository,
    user_id: uuid.UUID,
    *,
    tx_ids: list[uuid.UUID] | None = None,
    reanalyze_all: bool = False,
    use_ai_fallback: bool = True,
    ai_provider: AiProvider | None = None,
) -> CategorizationOutcome:
    """
    Execute layered categorization & merchant normalization for a user's eligible transactions.
    Never modifies FinancialTransaction.category_id silently without user confirmation.
    """
    provider = ai_provider or NullAiProvider()
    categories = repo.list_available_categories(db, user_id)
    categories_by_name: dict[str, FinancialCategory] = {
        c.name.lower(): c for c in categories
    }
    expense_cat_names = tuple(c.name for c in categories if c.category_type == "expense")
    income_cat_names = tuple(c.name for c in categories if c.category_type == "income")

    model_meta = repo.get_model_metadata(db, user_id)
    pipeline = load_user_pipeline(model_meta)
    model_version = model_meta.model_version if model_meta and model_meta.status == "trained" else None

    txs = repo.list_eligible_transactions(
        db,
        user_id,
        tx_ids=tx_ids,
        include_transfers=False,
    )

    outcome = CategorizationOutcome()

    # Reset merchant counters before full re-analysis to keep stats exact
    if reanalyze_all and not tx_ids:
        merchants, _ = repo.list_merchants(db, user_id, page=1, page_size=500)
        for m in merchants:
            m.transaction_count = 0
            m.total_spent = Decimal("0.00")
            db.add(m)
        db.flush()

    for tx in txs:
        existing_rec = repo.get_categorization_by_tx(db, user_id, tx.id)
        sig = _tx_signature(tx, use_ai_fallback, model_version)

        if (
            existing_rec is not None
            and not reanalyze_all
            and existing_rec.input_signature == sig
            and existing_rec.review_status in ("overridden", "confirmed", "auto_categorized")
        ):
            if existing_rec.review_status in ("overridden", "confirmed"):
                outcome.user_preserved += 1
            continue

        # Preserve explicit user overrides/confirmations unless missing merchant link
        if existing_rec and existing_rec.review_status in ("overridden", "confirmed"):
            merchant, _ = resolve_or_upsert_merchant(
                db,
                repo,
                user_id,
                description=tx.description,
                merchant_payee=tx.merchant_payee,
                amount=tx.amount,
                tx_type=tx.transaction_type,
                categories_by_name=categories_by_name,
            )
            existing_rec.merchant_id = existing_rec.merchant_id or merchant.id
            existing_rec.current_category_id = tx.category_id
            existing_rec.current_category_name = tx.category.name if tx.category else existing_rec.current_category_name
            existing_rec.input_signature = sig
            existing_rec.updated_at = dt.datetime.now(dt.UTC)
            db.add(existing_rec)
            outcome.processed += 1
            outcome.user_preserved += 1
            continue

        merchant, parsed_merchant = resolve_or_upsert_merchant(
            db,
            repo,
            user_id,
            description=tx.description,
            merchant_payee=tx.merchant_payee,
            amount=tx.amount,
            tx_type=tx.transaction_type,
            categories_by_name=categories_by_name,
        )

        # Layer 2: Authoritative user-confirmed merchant category mapping
        mapping: MerchantCategoryMapping | None = repo.get_merchant_category_mapping(
            db, user_id, merchant.id
        )
        suggested_cat: FinancialCategory | None = None
        method = "fallback"
        confidence = Decimal("0.3500")
        explanation = "No strong rule or pattern matched; marked for user review."
        evidence: dict = {"merchant_key": merchant.canonical_key, "signals": []}
        provider_used: str | None = "local"
        used_model_ver: str | None = None

        if mapping and mapping.is_authoritative:
            mapped_cat = repo.get_category_by_id(db, user_id, mapping.category_id)
            if mapped_cat and mapped_cat.category_type == tx.transaction_type:
                suggested_cat = mapped_cat
                method = "confirmed_mapping"
                confidence = Decimal("0.9800")
                explanation = (
                    f"Applied your confirmed merchant mapping for '{merchant.normalized_name}' -> '{mapped_cat.name}'."
                )
                evidence["signals"] = [f"authoritative_mapping:{merchant.canonical_key}"]

        # Layer 3: Deterministic India-first rules
        if suggested_cat is None:
            rule_cat, rule_conf, rule_exp, rule_signals = _match_deterministic_rule(
                tx, parsed_merchant, categories_by_name
            )
            if rule_cat is not None:
                suggested_cat = rule_cat
                method = "deterministic_rule"
                confidence = Decimal(str(round(rule_conf, 4)))
                explanation = rule_exp or f"Matched deterministic rule -> '{rule_cat.name}'."
                evidence["signals"] = rule_signals
                outcome.rule_matched += 1

        # Layer 4: Per-user ML Classifier (TF-IDF + LogisticRegression)
        if suggested_cat is None and pipeline is not None:
            ml_pred = predict_transaction_category(
                pipeline,
                tx,
                merchant.normalized_name,
                model_version=model_version or "v1",
            )
            if ml_pred and ml_pred.confidence >= Decimal("0.5800"):
                ml_cat = categories_by_name.get(ml_pred.category_name.lower())
                if ml_cat and ml_cat.category_type == tx.transaction_type:
                    suggested_cat = ml_cat
                    method = "ml_classifier"
                    confidence = ml_pred.confidence
                    explanation = (
                        f"Predicted by your personal TF-IDF classifier with {float(ml_pred.confidence) * 100:.0f}% confidence."
                    )
                    evidence["signals"] = ml_pred.top_alternatives
                    used_model_ver = ml_pred.model_version
                    outcome.ml_matched += 1

        # Layer 5: Optional Groq LLM fallback (only when ambiguous & provider enabled)
        if (
            suggested_cat is None
            and use_ai_fallback
            and provider.is_available()
            and not (existing_rec and existing_rec.input_signature == sig and existing_rec.provider_name == provider.provider_name)
        ):
            allowed = expense_cat_names if tx.transaction_type == "expense" else income_cat_names
            ai_res = provider.categorize_transaction(
                CategorizationAiInput(
                    transaction_type=tx.transaction_type,
                    sanitized_description=sanitize_text_for_ai(tx.description),
                    sanitized_merchant=sanitize_text_for_ai(tx.merchant_payee or merchant.normalized_name),
                    amount_band=_amount_band_label(tx.amount),
                    allowed_categories=allowed,
                )
            )
            outcome.llm_calls += 1
            if ai_res is not None:
                ai_cat = categories_by_name.get(ai_res.suggested_category.lower())
                if ai_cat and ai_cat.category_type == tx.transaction_type:
                    suggested_cat = ai_cat
                    method = "llm_fallback"
                    confidence = Decimal(str(round(ai_res.confidence, 4)))
                    explanation = ai_res.explanation
                    provider_used = provider.provider_name
                    used_model_ver = provider.model_name
                    evidence["signals"] = ["llm_structured_json"]
                    outcome.llm_matched += 1
                    if ai_res.normalized_merchant and not merchant.is_user_confirmed:
                        merchant.normalized_name = ai_res.normalized_merchant[:150]
                        db.add(merchant)

        # Layer 6: Default fallback to existing transaction category or Other
        if suggested_cat is None and tx.category is not None:
            suggested_cat = tx.category
            method = "existing_category"
            confidence = Decimal("0.5500")
            explanation = f"Retained transaction category '{tx.category.name}'; review if more specific category applies."

        # Decide review status:
        # Mark needs_review when low confidence, uncategorized, or suggestion differs from current category.
        current_cat_name = tx.category.name if tx.category else None
        differs_from_current = (
            suggested_cat is not None and tx.category_id != suggested_cat.id
        )
        is_generic = current_cat_name in (None, "Other Expenses", "Other Income")
        if suggested_cat is None or confidence < Decimal("0.7500") or differs_from_current or is_generic:
            review_status = "needs_review"
            outcome.needs_review += 1
        else:
            review_status = "auto_categorized"
            outcome.auto_categorized += 1

        rec = existing_rec or TransactionCategorization(
            user_id=user_id,
            transaction_id=tx.id,
        )
        rec.merchant_id = merchant.id
        rec.current_category_id = tx.category_id
        rec.current_category_name = current_cat_name
        rec.suggested_category_id = suggested_cat.id if suggested_cat else None
        rec.suggested_category_name = suggested_cat.name if suggested_cat else None
        rec.predicted_category_name = suggested_cat.name if suggested_cat else None
        rec.classification_method = method
        rec.confidence = confidence
        rec.explanation = explanation
        rec.evidence = evidence
        rec.model_version = used_model_ver
        rec.provider_name = provider_used
        rec.review_status = review_status
        rec.input_signature = sig
        rec.analyzed_at = dt.datetime.now(dt.UTC)
        rec.updated_at = dt.datetime.now(dt.UTC)
        db.add(rec)
        outcome.processed += 1

    db.flush()
    return outcome
