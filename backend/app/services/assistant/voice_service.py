import datetime as dt
import re
import shutil
import subprocess
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


_MAX_AUDIO_BYTES = 8 * 1024 * 1024  # 8 MB cap


def transcribe_voice_audio(
    audio_bytes: bytes,
    *,
    filename: str = "recording.webm",
    content_type: str = "audio/webm",
) -> tuple[str, str]:
    """
    Transcribe browser microphone audio using server-side Groq Whisper (`whisper-large-v3-turbo`).
    Audio stays transient in memory and is never persisted to disk.
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

    try:
        client = provider._get_client()
        result = client.audio.transcriptions.create(
            file=(safe_name, audio_bytes, mime),
            model="whisper-large-v3-turbo",
            language="en",
            temperature=0.0,
        )
        transcript = (getattr(result, "text", None) or "").strip()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Speech transcription failed: {exc}",
        ) from exc

    return transcript, "groq:whisper-large-v3-turbo"


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
