import datetime as dt
import os
import re
import shutil
import subprocess
import tempfile
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.forecasting.forecast_repository import ForecastRepository
from app.repositories.intelligence.intelligence_repository import IntelligenceRepository
from app.schemas.assistant import VoiceExpenseDraftResponse
from app.services.ai.categorization_service import EXPENSE_KEYWORD_RULES, INCOME_KEYWORD_RULES
from app.services.ai.groq_provider import GroqAiProvider
from app.services.ai.merchant_intelligence import normalize_merchant_text
from app.services.bills.status_engine import resolve_user_today

_AMOUNT_RE = re.compile(
    r"(?:₹|rs\.?|inr|rupees?)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)|([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*(?:rs\.?|inr|rupees?)",
    re.I,
)
_FALLBACK_NUM_RE = re.compile(r"\b([0-9]+(?:\.[0-9]{1,2})?)\b")

_SYNONYMS: dict[str, str] = {
    "lunch": "Food & Dining",
    "dinner": "Food & Dining",
    "breakfast": "Food & Dining",
    "snacks": "Food & Dining",
    "food": "Food & Dining",
    "cab": "Transportation",
    "petrol": "Transportation",
    "fuel": "Transportation",
    "auto": "Transportation",
    "groceries": "Groceries",
    "grocery": "Groceries",
    "electricity": "Utilities & Bills",
    "recharge": "Utilities & Bills",
    "medicine": "Healthcare",
    "pharmacy": "Healthcare",
}


def parse_voice_expense_transcript(
    db: Session, user: User, transcript: str
) -> VoiceExpenseDraftResponse:
    """
    Parse spoken financial transcript into an editable expense/income draft without ever
    creating or modifying FinancialTransaction records directly.
    Leaves ambiguous/missing fields explicit in missing_fields for user review.
    """
    text = (transcript or "").strip()
    lower = text.lower()
    fc_repo = ForecastRepository()
    intel_repo = IntelligenceRepository()

    tz = fc_repo.get_user_timezone(db, user.id)
    today = resolve_user_today(tz)

    tx_date = today
    if "yesterday" in lower:
        tx_date = today - dt.timedelta(days=1)

    tx_type = "income" if any(k in lower for k in ("received salary", "got paid", "income", "refund received", "cashback")) else "expense"

    amount: Decimal | None = None
    m = _AMOUNT_RE.search(text)
    if m:
        raw_num = (m.group(1) or m.group(2) or "").replace(",", "")
        try:
            cand = Decimal(raw_num)
            if cand > Decimal("0"):
                amount = cand.quantize(Decimal("0.01"))
        except InvalidOperation:
            amount = None
    elif (m2 := _FALLBACK_NUM_RE.search(text)) is not None:
        try:
            cand = Decimal(m2.group(1))
            if cand > Decimal("0"):
                amount = cand.quantize(Decimal("0.01"))
        except InvalidOperation:
            amount = None

    # Match existing user-owned category cleanly without inventing one
    categories = intel_repo.list_available_categories(db, user.id)
    cat_by_name = {c.name.lower(): c for c in categories if c.category_type == tx_type}
    matched_cat = None

    for kw, target_cat_name in _SYNONYMS.items():
        if kw in lower and target_cat_name.lower() in cat_by_name:
            matched_cat = cat_by_name[target_cat_name.lower()]
            break

    if matched_cat is None:
        rules = INCOME_KEYWORD_RULES if tx_type == "income" else EXPENSE_KEYWORD_RULES
        for cat_name, kws, _ in rules:
            if any(kw in lower for kw in kws) and cat_name.lower() in cat_by_name:
                matched_cat = cat_by_name[cat_name.lower()]
                break

    # Match user account ONLY if explicitly named in transcript (never fabricate)
    accounts = fc_repo.list_active_accounts(db, user.id)
    matched_acc = None
    for acc in accounts:
        if acc.name.lower() in lower:
            matched_acc = acc
            break
    if matched_acc is None and "cash" in lower:
        cash_matches = [a for a in accounts if a.account_type == "cash" or "cash" in a.name.lower()]
        if len(cash_matches) == 1:
            matched_acc = cash_matches[0]

    # Clean description from transcript
    cleaned_desc = _AMOUNT_RE.sub("", text)
    cleaned_desc = re.sub(
        r"\b(?:i|spent|paid|for|on|using|via|from|my|account|today|yesterday)\b",
        " ",
        cleaned_desc,
        flags=re.I,
    )
    cleaned_desc = re.sub(r"\s+", " ", cleaned_desc).strip(" .,")
    if not cleaned_desc:
        cleaned_desc = matched_cat.name if matched_cat else text[:120]

    norm_merch = normalize_merchant_text(text, cleaned_desc)
    merchant_payee = (
        norm_merch.normalized_name if norm_merch.canonical_key != "unknown_merchant" else None
    )

    missing_fields: list[str] = []
    if amount is None:
        missing_fields.append("amount")
    if matched_acc is None:
        missing_fields.append("account_id")
    if matched_cat is None:
        missing_fields.append("category_id")

    return VoiceExpenseDraftResponse(
        transcript=text,
        transaction_type=tx_type,
        amount=amount,
        currency="INR",
        category_id=matched_cat.id if matched_cat else None,
        category_name=matched_cat.name if matched_cat else None,
        account_id=matched_acc.id if matched_acc else None,
        account_name=matched_acc.name if matched_acc else None,
        description=cleaned_desc[:200],
        merchant_payee=merchant_payee,
        transaction_date=tx_date,
        missing_fields=missing_fields,
        requires_user_confirmation=True,
        notes="Voice draft requires explicit review and Save Transaction confirmation.",
    )


_BILL_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("electricity", ("electricity", "electric", "power bill", "bescom", "mahadiscom", "tata power", "eb bill")),
    ("water", ("water", "jal board", "bwssb")),
    ("gas", ("gas", "piped gas", "lpg", "cylinder", "indane", "hp gas", "bharat gas")),
    ("internet", ("internet", "broadband", "wifi", "wi-fi", "fiber", "airtel xstream", "jiofiber", "act fibernet")),
    ("mobile_postpaid", ("postpaid", "mobile bill", "phone bill")),
    ("mobile_recharge", ("recharge", "prepaid")),
    ("rent", ("rent", "house rent", "pg rent", "lease")),
    ("insurance", ("insurance", "lic", "health policy", "car insurance")),
    ("loan_emi", ("emi", "loan payment", "home loan", "car loan")),
    ("credit_card", ("credit card", "card bill")),
    ("maintenance", ("maintenance", "society", "hoa")),
]

_ACTION_CREATE_VERBS = re.compile(
    r"\b(?:add|create|log|record|schedule|set\s+up|remind(?:\s+me)?\s+to\s+pay|paid|spent)\b",
    re.I,
)


def _extract_relative_date(text: str, today: dt.date) -> tuple[dt.date, bool]:
    lower = text.lower()
    if "today" in lower:
        return today, True
    if "tomorrow" in lower:
        return today + dt.timedelta(days=1), True
    if "yesterday" in lower:
        return today - dt.timedelta(days=1), True
    if "next week" in lower:
        return today + dt.timedelta(days=7), True
    if "next month" in lower:
        return today + dt.timedelta(days=30), True
    m_days = re.search(r"\bin\s+(\d{1,3})\s+days?\b", lower)
    if m_days:
        return today + dt.timedelta(days=min(int(m_days.group(1)), 365)), True
    m_weeks = re.search(r"\bin\s+(\d{1,2})\s+weeks?\b", lower)
    if m_weeks:
        return today + dt.timedelta(days=min(int(m_weeks.group(1)) * 7, 365)), True
    m_iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", lower)
    if m_iso:
        try:
            return dt.date.fromisoformat(m_iso.group(1)), True
        except ValueError:
            pass
    return today + dt.timedelta(days=7), False


def _extract_amount(text: str) -> Decimal | None:
    m = _AMOUNT_RE.search(text)
    if m:
        raw_num = (m.group(1) or m.group(2) or "").replace(",", "")
        try:
            cand = Decimal(raw_num)
            if cand > Decimal("0"):
                return cand.quantize(Decimal("0.01"))
        except InvalidOperation:
            pass
    m2 = _FALLBACK_NUM_RE.search(text)
    if m2:
        try:
            cand = Decimal(m2.group(1))
            if cand > Decimal("0"):
                return cand.quantize(Decimal("0.01"))
        except InvalidOperation:
            pass
    return None


def try_parse_chat_action_draft(
    db: Session, user: User, message: str
) -> dict | None:
    """
    Detect explicit user requests in chat to create a Bill or Expense/Income Transaction,
    returning a structured confirmation-required `draft_action` dict without mutating DB state.
    """
    text = (message or "").strip()
    lower = text.lower()
    if not text or not _ACTION_CREATE_VERBS.search(lower):
        return None

    # Ignore analytical/question prompts like "How much did I spend..." or "Should I add..."
    if text.endswith("?") or re.match(r"^(?:how|what|why|when|should|can\s+you\s+explain)\b", lower):
        return None

    fc_repo = ForecastRepository()
    tz = fc_repo.get_user_timezone(db, user.id)
    today = resolve_user_today(tz)

    is_bill_intent = bool(
        re.search(r"\b(?:bill|due|electricity|water\s+bill|gas\s+bill|internet\s+bill|broadband|wifi\s+bill|postpaid|rent\s+due|remind\s+me\s+to\s+pay)\b", lower)
    )
    if is_bill_intent and not re.search(r"\b(?:spent|paid)\b", lower):
        amount = _extract_amount(text)
        due_date, _ = _extract_relative_date(text, today)

        bill_category = "other"
        for cat, kws in _BILL_CATEGORY_KEYWORDS:
            if any(k in lower for k in kws):
                bill_category = cat
                break

        cat_titles = {
            "electricity": "Electricity Bill",
            "water": "Water Bill",
            "gas": "Gas Bill",
            "internet": "Internet / Broadband Bill",
            "mobile_postpaid": "Mobile Postpaid Bill",
            "mobile_recharge": "Mobile Recharge",
            "rent": "Rent Bill",
            "insurance": "Insurance Premium",
            "loan_emi": "Loan EMI",
            "credit_card": "Credit Card Bill",
            "maintenance": "Maintenance Bill",
            "other": "Utility / Scheduled Bill",
        }
        bill_name = cat_titles[bill_category]
        bill_type = "recurring" if any(k in lower for k in ("every month", "monthly", "recurring", "weekly", "yearly")) else "one_time"
        frequency = None
        if bill_type == "recurring":
            if "weekly" in lower:
                frequency = "weekly"
            elif "yearly" in lower or "annual" in lower:
                frequency = "yearly"
            else:
                frequency = "monthly"

        missing: list[str] = []
        if amount is None:
            missing.append("expected_amount")

        return {
            "action_type": "create_bill",
            "execution_status": "pending_confirmation",
            "bill_name": bill_name,
            "bill_category": bill_category,
            "provider_name": None,
            "bill_type": bill_type,
            "frequency": frequency,
            "expected_amount": str(amount) if amount is not None else None,
            "currency": "INR",
            "due_date": due_date.isoformat(),
            "description": text[:240],
            "missing_fields": missing,
            "requires_user_confirmation": True,
        }

    # Check OTT / recurring Subscription intent
    ott_catalog: list[tuple[str, str, str]] = [
        ("netflix", "Netflix", "ott_streaming"),
        ("amazon prime", "Amazon Prime Video", "ott_streaming"),
        ("prime video", "Amazon Prime Video", "ott_streaming"),
        ("hotstar", "Disney+ Hotstar", "ott_streaming"),
        ("disney", "Disney+ Hotstar", "ott_streaming"),
        ("sonyliv", "SonyLIV", "ott_streaming"),
        ("sony liv", "SonyLIV", "ott_streaming"),
        ("zee5", "ZEE5", "ott_streaming"),
        ("jiocinema", "JioCinema", "ott_streaming"),
        ("jio cinema", "JioCinema", "ott_streaming"),
        ("youtube premium", "YouTube Premium", "ott_streaming"),
        ("spotify", "Spotify", "music"),
        ("apple music", "Apple Music", "music"),
        ("icloud", "iCloud Storage", "cloud_storage"),
        ("google one", "Google One", "cloud_storage"),
        ("chatgpt", "ChatGPT Plus", "software_saas"),
        ("swiggy one", "Swiggy One", "delivery_membership"),
        ("zomato gold", "Zomato Gold", "delivery_membership"),
        ("gym", "Gym Membership", "fitness"),
    ]
    matched_ott = next((item for item in ott_catalog if item[0] in lower), None)
    is_sub_intent = bool(
        matched_ott
        or re.search(r"\b(?:ott|subscription|subscribe|streaming|plan|membership)\b", lower)
    )
    if is_sub_intent and not re.search(r"\b(?:spent|paid)\b", lower):
        amount = _extract_amount(text)
        sub_name = matched_ott[1] if matched_ott else "OTT Subscription"
        sub_cat = matched_ott[2] if matched_ott else "ott_streaming"
        billing_frequency = "monthly"
        if "yearly" in lower or "annual" in lower or "per year" in lower:
            billing_frequency = "yearly"
        elif "quarterly" in lower:
            billing_frequency = "quarterly"
        elif "weekly" in lower or "per week" in lower:
            billing_frequency = "weekly"
        elif "half yearly" in lower or "6 months" in lower:
            billing_frequency = "half_yearly"

        due_date, has_explicit_date = _extract_relative_date(text, today)
        from app.services.subscriptions.subscription_math import advance_subscription_renewal

        next_renewal = (
            due_date
            if has_explicit_date
            else advance_subscription_renewal(today, billing_frequency, today.day)
        )
        missing = ["amount"] if amount is None else []

        return {
            "action_type": "create_subscription",
            "execution_status": "pending_confirmation",
            "subscription_name": sub_name,
            "provider_name": sub_name,
            "category": sub_cat,
            "amount": str(amount) if amount is not None else None,
            "currency": "INR",
            "billing_frequency": billing_frequency,
            "start_date": today.isoformat(),
            "next_renewal_date": next_renewal.isoformat(),
            "description": text[:240],
            "missing_fields": missing,
            "requires_user_confirmation": True,
        }

    # Otherwise check explicit expense/income entry command
    if re.search(r"\b(?:spent|paid|add\s+(?:an?\s+)?(?:expense|income|transaction)|log\s+(?:an?\s+)?(?:expense|income)|record\s+(?:an?\s+)?(?:expense|income))\b", lower):
        tx_draft = parse_voice_expense_transcript(db, user, text)
        return {
            "action_type": "create_transaction",
            "execution_status": "pending_confirmation",
            "transcript": tx_draft.transcript,
            "transaction_type": tx_draft.transaction_type,
            "amount": str(tx_draft.amount) if tx_draft.amount is not None else None,
            "currency": tx_draft.currency,
            "category_id": str(tx_draft.category_id) if tx_draft.category_id else None,
            "category_name": tx_draft.category_name,
            "account_id": str(tx_draft.account_id) if tx_draft.account_id else None,
            "account_name": tx_draft.account_name,
            "description": tx_draft.description,
            "merchant_payee": tx_draft.merchant_payee,
            "transaction_date": tx_draft.transaction_date.isoformat(),
            "missing_fields": tx_draft.missing_fields,
            "requires_user_confirmation": True,
        }

    return None


def execute_chat_action_draft(
    db: Session,
    user: User,
    draft_action: dict,
    *,
    overrides: dict | None = None,
    execution_mode: str = "confirmed",
    raise_on_incomplete: bool = True,
) -> tuple[dict, bool]:
    """
    Execute a structured chat draft action (`create_bill`, `create_subscription`, or `create_transaction`)
    against the authoritative Phase 2/5/6 domain services and return `(updated_draft, was_executed)`.
    Enforces idempotency so an already-executed draft is never duplicated.
    """
    updated = dict(draft_action or {})
    if updated.get("execution_status") == "executed":
        if raise_on_incomplete:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This action has already been saved. Duplicate execution blocked.",
            )
        return updated, False

    if overrides:
        for k, v in overrides.items():
            if v is not None:
                updated[k] = str(v) if not isinstance(v, (str, bool, int, float)) else v

    action_type = updated.get("action_type")
    if action_type == "create_bill":
        from app.schemas.bills import BillCreateRequest
        from app.services.bills.bill_service import BillService

        raw_amt = updated.get("expected_amount")
        if raw_amt is None or Decimal(str(raw_amt)) <= Decimal("0"):
            if raise_on_incomplete:
                raise HTTPException(status_code=400, detail="Valid positive bill amount is required.")
            return updated, False

        amt = Decimal(str(raw_amt)).quantize(Decimal("0.01"))
        due = dt.date.fromisoformat(str(updated["due_date"]))
        bill_name = str(updated.get("bill_name") or "Scheduled Bill").strip()
        bill_type = str(updated.get("bill_type") or "one_time")
        freq = updated.get("frequency") if bill_type == "recurring" else None

        req = BillCreateRequest(
            bill_name=bill_name,
            bill_category=str(updated.get("bill_category") or "other"),  # type: ignore[arg-type]
            provider_name=updated.get("provider_name") or None,
            description=updated.get("description") or f"Created via AI Assistant: {bill_name}",
            bill_type=bill_type,  # type: ignore[arg-type]
            frequency=freq,  # type: ignore[arg-type]
            is_variable_amount=False,
            expected_amount=amt,
            current_amount=amt,
            currency="INR",
            due_date=due,
            reminder_enabled=True,
        )
        created = BillService().create_bill(db, user, req)
        updated["execution_status"] = "executed"
        updated["execution_mode"] = execution_mode
        updated["created_id"] = str(created.id)
        updated["bill_name"] = created.bill_name
        updated["bill_category"] = created.bill_category
        updated["expected_amount"] = str(amt)
        updated["due_date"] = created.due_date.isoformat()
        updated["executed_label"] = f"{created.bill_name} (₹{amt}, due {created.due_date.isoformat()})"
        updated["requires_user_confirmation"] = False
        return updated, True

    if action_type == "create_subscription":
        from app.schemas.subscriptions import SubscriptionCreateRequest
        from app.services.subscriptions.subscription_service import SubscriptionService

        raw_amt = updated.get("amount")
        if raw_amt is None or Decimal(str(raw_amt)) <= Decimal("0"):
            if raise_on_incomplete:
                raise HTTPException(
                    status_code=400, detail="Valid positive subscription amount is required."
                )
            return updated, False

        amt = Decimal(str(raw_amt)).quantize(Decimal("0.01"))
        start_d = dt.date.fromisoformat(str(updated.get("start_date") or dt.date.today().isoformat()))
        next_d = dt.date.fromisoformat(str(updated.get("next_renewal_date") or start_d.isoformat()))
        sub_name = str(updated.get("subscription_name") or "OTT Subscription").strip()
        billing_freq = str(updated.get("billing_frequency") or "monthly")

        req = SubscriptionCreateRequest(
            subscription_name=sub_name,
            provider_name=updated.get("provider_name") or sub_name,
            category=str(updated.get("category") or "ott_streaming"),  # type: ignore[arg-type]
            description=updated.get("description") or f"Created via AI Assistant: {sub_name}",
            amount=amt,
            currency="INR",
            billing_frequency=billing_freq,  # type: ignore[arg-type]
            start_date=start_d,
            next_renewal_date=next_d,
            reminder_enabled=True,
        )
        created_sub = SubscriptionService().create_subscription(db, user, req)
        updated["execution_status"] = "executed"
        updated["execution_mode"] = execution_mode
        updated["created_id"] = str(created_sub.id)
        updated["subscription_name"] = created_sub.subscription_name
        updated["category"] = created_sub.category
        updated["amount"] = str(amt)
        updated["billing_frequency"] = created_sub.billing_frequency
        updated["next_renewal_date"] = created_sub.next_renewal_date.isoformat()
        updated["executed_label"] = (
            f"{created_sub.subscription_name} (₹{amt}/{created_sub.billing_frequency}, next {created_sub.next_renewal_date.isoformat()})"
        )
        updated["requires_user_confirmation"] = False
        return updated, True

    if action_type == "create_transaction":
        import uuid as _uuid

        from app.schemas.finance.transaction import TransactionCreateRequest
        from app.services.finance.transaction_service import TransactionService

        raw_amt = updated.get("amount")
        raw_acc = updated.get("account_id")
        if raw_amt is None or Decimal(str(raw_amt)) <= Decimal("0") or not raw_acc:
            if raise_on_incomplete:
                raise HTTPException(
                    status_code=400,
                    detail="Account and positive amount are required to record a transaction.",
                )
            return updated, False

        amt = Decimal(str(raw_amt)).quantize(Decimal("0.01"))
        tx_date = dt.date.fromisoformat(str(updated.get("transaction_date") or dt.date.today().isoformat()))
        cat_raw = updated.get("category_id")
        req = TransactionCreateRequest(
            account_id=_uuid.UUID(str(raw_acc)),
            transaction_type=str(updated.get("transaction_type") or "expense"),  # type: ignore[arg-type]
            amount=amt,
            currency="INR",
            category_id=_uuid.UUID(str(cat_raw)) if cat_raw else None,
            description=str(updated.get("description") or "Assistant transaction")[:250],
            merchant_payee=updated.get("merchant_payee") or None,
            transaction_date=tx_date,
            notes=updated.get("notes") or None,
        )
        created_tx = TransactionService().create_transaction(
            db=db, user=user, req=req, source="manual", commit=True
        )
        updated["execution_status"] = "executed"
        updated["execution_mode"] = execution_mode
        updated["created_id"] = str(created_tx.id)
        updated["amount"] = str(amt)
        updated["executed_label"] = f"{created_tx.description} (₹{amt})"
        updated["requires_user_confirmation"] = False
        return updated, True

    if raise_on_incomplete:
        raise HTTPException(status_code=400, detail=f"Unsupported draft action '{action_type}'.")
    return updated, False


_MAX_AUDIO_BYTES = 8 * 1024 * 1024  # 8 MB cap


def _normalize_audio_to_wav(audio_bytes: bytes, suffix: str) -> bytes | None:
    """
    Convert browser MediaRecorder containers (webm/ogg/mp4/opus) to 16 kHz mono PCM WAV via ffmpeg
    so Whisper never fails on partial container headers. Returns None cleanly if ffmpeg is unavailable
    or input bytes are non-audio stubs (e.g. unit test mocks).
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin or not audio_bytes:
        return None
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
            tf.write(audio_bytes)
            tmp_path = tf.name
        proc = subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-v",
                "error",
                "-i",
                tmp_path,
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                "-f",
                "wav",
                "pipe:1",
            ],
            capture_output=True,
            timeout=12,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.startswith(b"RIFF") and len(proc.stdout) > 44:
            return proc.stdout
    except Exception:
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    return None


def transcribe_voice_audio(
    audio_bytes: bytes,
    *,
    filename: str = "recording.webm",
    content_type: str = "audio/webm",
) -> tuple[str, str]:
    """
    Transcribe browser microphone audio using server-side Groq Whisper (`whisper-large-v3-turbo`
    with `whisper-large-v3` fallback). Audio stays transient and is never persisted.
    """
    if not audio_bytes or len(audio_bytes) < 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recorded audio is empty. Please speak clearly and try again.",
        )
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Audio recording exceeds 8 MB limit.",
        )

    provider = GroqAiProvider()
    if not provider.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server speech-to-text (Groq Whisper) is disabled or unconfigured.",
        )

    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", filename or "recording.webm")[:60]
    if "." not in safe_name:
        safe_name = f"{safe_name}.webm"
    mime = (content_type or "audio/webm").split(";")[0].strip()

    ext = f".{safe_name.rsplit('.', 1)[-1]}"
    wav_bytes = _normalize_audio_to_wav(audio_bytes, ext) if mime != "audio/wav" else None
    upload_tuple = (
        ("recording.wav", wav_bytes, "audio/wav")
        if wav_bytes is not None
        else (safe_name, audio_bytes, mime)
    )

    last_exc: Exception | None = None
    client = provider._get_client()
    for stt_model in ("whisper-large-v3-turbo", "whisper-large-v3"):
        try:
            result = client.audio.transcriptions.create(
                file=upload_tuple,
                model=stt_model,
                language="en",
                prompt=(
                    "Indian personal finance, INR, rupees, lakh, EMI, UPI, HDFC, ICICI, SBI, "
                    "Swiggy, Zomato, BESCOM, Netflix, JioHotstar, Sony TV, MacBook, rent, bill."
                ),
                temperature=0.0,
            )
            transcript = (getattr(result, "text", None) or "").strip()
            return transcript, f"groq:{stt_model}"
        except Exception as exc:
            last_exc = exc
            continue

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Speech transcription failed: {last_exc}",
    ) from last_exc


def synthesize_voice_speech(raw_text: str) -> bytes:
    """
    Synthesize clean WAV audio locally via `espeak-ng` so Read Aloud works reliably
    even when browser speechSynthesis has no working OS voice bridge.
    """
    clean = re.sub(r"[\x00-\x1f\x7f]+", " ", raw_text or "").strip()
    if not clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Speech text cannot be empty.",
        )
    clean = clean[:1800]

    espeak_bin = shutil.which("espeak-ng") or shutil.which("espeak")
    if not espeak_bin:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local speech synthesizer (espeak-ng) is unavailable on the server.",
        )

    for voice_flag in ("en-in", "en"):
        try:
            proc = subprocess.run(
                [espeak_bin, "-v", voice_flag, "-s", "160", "--stdin", "--stdout"],
                input=clean.encode("utf-8"),
                capture_output=True,
                timeout=8,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.startswith(b"RIFF"):
                return proc.stdout
        except subprocess.TimeoutExpired:
            continue

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unable to generate Read Aloud audio.",
    )
