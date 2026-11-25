import re
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.finance import FinancialCategory
from app.models.intelligence import MerchantAlias, MerchantIdentity
from app.repositories.intelligence.intelligence_repository import IntelligenceRepository

# Strip common Indian banking/UPI noise tokens while retaining meaningful merchant tokens
_NOISE_PATTERNS = [
    re.compile(r"\b(?:UPI|IMPS|NEFT|RTGS|POS|ATW|ATM|ECOM|NACH|ACH|ECS|SI|MANDATE|INTL|TXN|REF|UTR|RRN)\b", re.I),
    re.compile(r"\b(?:CR|DR|DEBIT|CREDIT|PAID|PAYMENT|VIA|TO|FROM|BY|FOR|ON|THE|PVT|LTD|INDIA|PRIVATE|LIMITED|INC|LLP)\b", re.I),
    re.compile(r"@[a-z0-9.\-_]+", re.I),  # UPI VPA domain like @okaxis, @ybl, @icici
    re.compile(r"\b\d{4,}\b"),  # Long numbers / refs / dates / order IDs
    re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"),
]


@dataclass(frozen=True)
class CanonicalMerchantRule:
    canonical_key: str
    display_name: str
    default_category: str
    keywords: tuple[str, ...]


# Known Indian & global merchants for deterministic canonical normalization
KNOWN_MERCHANTS: tuple[CanonicalMerchantRule, ...] = (
    # Food & Dining
    CanonicalMerchantRule("swiggy", "Swiggy", "Food & Dining", ("swiggy", "bundl technologies")),
    CanonicalMerchantRule("zomato", "Zomato", "Food & Dining", ("zomato", "eternal ltd")),
    CanonicalMerchantRule("dominos", "Domino's Pizza", "Food & Dining", ("dominos", "jubilant foodworks")),
    CanonicalMerchantRule("starbucks", "Starbucks", "Food & Dining", ("starbucks", "tata starbucks")),
    CanonicalMerchantRule("mcdonalds", "McDonald's", "Food & Dining", ("mcdonald",)),
    CanonicalMerchantRule("kfc", "KFC", "Food & Dining", ("kfc",)),
    CanonicalMerchantRule("chai_point", "Chai Point", "Food & Dining", ("chai point", "chaipoint")),
    # Groceries
    CanonicalMerchantRule("blinkit", "Blinkit", "Groceries", ("blinkit", "grofers")),
    CanonicalMerchantRule("zepto", "Zepto", "Groceries", ("zepto", "kiranakart")),
    CanonicalMerchantRule("bigbasket", "BigBasket", "Groceries", ("bigbasket", "supermarket grocery")),
    CanonicalMerchantRule("swiggy_instamart", "Swiggy Instamart", "Groceries", ("instamart",)),
    CanonicalMerchantRule("dmart", "DMart", "Groceries", ("dmart", "avenue supermarts")),
    CanonicalMerchantRule("reliance_fresh", "Reliance Fresh / Smart", "Groceries", ("reliance fresh", "reliance smart", "jiomart")),
    CanonicalMerchantRule("country_delight", "Country Delight", "Groceries", ("country delight",)),
    # Transportation
    CanonicalMerchantRule("uber", "Uber", "Transportation", ("uber",)),
    CanonicalMerchantRule("ola", "Ola", "Transportation", ("ola cabs", "olacabs", "ani technologies", "ola electric")),
    CanonicalMerchantRule("rapido", "Rapido", "Transportation", ("rapido", "roppen")),
    CanonicalMerchantRule("metro", "Metro Rail", "Transportation", ("metro", "bmrcl", "dmrc", "mmrc", "cmrl")),
    CanonicalMerchantRule("iocl", "IndianOil", "Transportation", ("indianoil", "iocl")),
    CanonicalMerchantRule("bpcl", "Bharat Petroleum", "Transportation", ("bpcl", "bharat petroleum")),
    CanonicalMerchantRule("hpcl", "Hindustan Petroleum", "Transportation", ("hpcl", "hindustan petroleum")),
    CanonicalMerchantRule("fastag", "FASTag Toll", "Transportation", ("fastag", "ihmcl", "netc")),
    # Subscriptions & OTT
    CanonicalMerchantRule("netflix", "Netflix", "Subscriptions", ("netflix",)),
    CanonicalMerchantRule("amazon_prime", "Amazon Prime", "Subscriptions", ("amazon prime", "prime video")),
    CanonicalMerchantRule("jiohotstar", "JioHotstar", "Subscriptions", ("hotstar", "jiohotstar", "novi digital")),
    CanonicalMerchantRule("spotify", "Spotify", "Subscriptions", ("spotify",)),
    CanonicalMerchantRule("youtube_premium", "YouTube Premium", "Subscriptions", ("youtube premium", "google youtube")),
    CanonicalMerchantRule("sonyliv", "SonyLIV", "Subscriptions", ("sonyliv", "sony liv")),
    CanonicalMerchantRule("zee5", "ZEE5", "Subscriptions", ("zee5",)),
    CanonicalMerchantRule("apple_services", "Apple Services", "Subscriptions", ("apple.com/bill", "itunes", "icloud")),
    CanonicalMerchantRule("google_one", "Google One / Play", "Subscriptions", ("google one", "google play")),
    CanonicalMerchantRule("openai_chatgpt", "OpenAI / ChatGPT", "Subscriptions", ("openai", "chatgpt")),
    CanonicalMerchantRule("microsoft_365", "Microsoft 365", "Subscriptions", ("microsoft",)),
    CanonicalMerchantRule("adobe", "Adobe Creative Cloud", "Subscriptions", ("adobe",)),
    # Shopping
    CanonicalMerchantRule("amazon", "Amazon", "Shopping", ("amazon pay", "amazon seller", "amazon.in", "amzn", "amazon")),
    CanonicalMerchantRule("flipkart", "Flipkart", "Shopping", ("flipkart",)),
    CanonicalMerchantRule("myntra", "Myntra", "Shopping", ("myntra",)),
    CanonicalMerchantRule("ajio", "AJIO", "Shopping", ("ajio",)),
    CanonicalMerchantRule("nykaa", "Nykaa", "Shopping", ("nykaa",)),
    CanonicalMerchantRule("meesho", "Meesho", "Shopping", ("meesho",)),
    CanonicalMerchantRule("croma", "Croma", "Shopping", ("croma", "infiniti retail")),
    CanonicalMerchantRule("decathlon", "Decathlon", "Shopping", ("decathlon",)),
    # Utilities & Telecom
    CanonicalMerchantRule("airtel", "Airtel", "Utilities & Bills", ("airtel", "bharti airtel")),
    CanonicalMerchantRule("jio", "Jio", "Utilities & Bills", ("jio recharge", "reliance jio", "myjio", "jiofiber")),
    CanonicalMerchantRule("vi_vodafone", "Vi (Vodafone Idea)", "Utilities & Bills", ("vodafone", "vi postpaid", "vi prepaid")),
    CanonicalMerchantRule("act_fibernet", "ACT Fibernet", "Utilities & Bills", ("act fibernet", "atria convergence")),
    CanonicalMerchantRule("bescom", "BESCOM Electricity", "Utilities & Bills", ("bescom",)),
    CanonicalMerchantRule("tata_power", "Tata Power", "Utilities & Bills", ("tata power",)),
    CanonicalMerchantRule("adani_electricity", "Adani Electricity", "Utilities & Bills", ("adani electricity",)),
    CanonicalMerchantRule("mahanagar_gas", "Mahanagar Gas", "Utilities & Bills", ("mahanagar gas", "mgl")),
    CanonicalMerchantRule("indane_gas", "Indane / Bharat Gas", "Utilities & Bills", ("indane", "bharatgas", "hp gas")),
    # Healthcare
    CanonicalMerchantRule("apollo", "Apollo Pharmacy / Hospital", "Healthcare", ("apollo pharmacy", "apollo hospital", "apollo")),
    CanonicalMerchantRule("pharmeasy", "PharmEasy", "Healthcare", ("pharmeasy",)),
    CanonicalMerchantRule("tata_1mg", "Tata 1mg", "Healthcare", ("1mg", "tata 1mg")),
    CanonicalMerchantRule("practo", "Practo", "Healthcare", ("practo",)),
    CanonicalMerchantRule("medplus", "MedPlus", "Healthcare", ("medplus",)),
    # Travel
    CanonicalMerchantRule("irctc", "IRCTC", "Travel", ("irctc",)),
    CanonicalMerchantRule("indigo", "IndiGo Airlines", "Travel", ("indigo", "interglobe aviation")),
    CanonicalMerchantRule("air_india", "Air India", "Travel", ("air india",)),
    CanonicalMerchantRule("makemytrip", "MakeMyTrip", "Travel", ("makemytrip", "mmt")),
    CanonicalMerchantRule("goibibo", "Goibibo", "Travel", ("goibibo",)),
    CanonicalMerchantRule("redbus", "redBus", "Travel", ("redbus",)),
    # Entertainment
    CanonicalMerchantRule("bookmyshow", "BookMyShow", "Entertainment", ("bookmyshow", "bigtree")),
    CanonicalMerchantRule("pvr_inox", "PVR INOX", "Entertainment", ("pvr", "inox")),
    # Insurance & Loan Interest
    CanonicalMerchantRule("lic", "LIC India", "Insurance", ("lic of india", "lic india", "lic premium")),
    CanonicalMerchantRule("hdfc_ergo", "HDFC ERGO / Life", "Insurance", ("hdfc ergo", "hdfc life")),
    CanonicalMerchantRule("icici_lombard", "ICICI Lombard / Prudential", "Insurance", ("icici lombard", "icici prudential")),
    CanonicalMerchantRule("bajaj_finserv", "Bajaj Finserv EMI", "Loan Interest", ("bajaj finserv", "bajaj finance")),
)


@dataclass
class NormalizedMerchantResult:
    canonical_key: str
    normalized_name: str
    raw_pattern: str
    normalized_token: str
    known_default_category: str | None


def normalize_merchant_text(raw_text: str | None, merchant_payee: str | None = None) -> NormalizedMerchantResult:
    """
    Deterministically clean Indian bank statement/UPI text into a stable canonical merchant key
    and human-readable display name.
    """
    primary_raw = (merchant_payee or "").strip() or (raw_text or "").strip()
    combined_lower = f"{merchant_payee or ''} {raw_text or ''}".lower()

    # Check known merchant canonical rules first (order-preserving specificity)
    for rule in KNOWN_MERCHANTS:
        for kw in rule.keywords:
            if kw in combined_lower:
                cleaned_token = _clean_token(primary_raw) or rule.canonical_key
                return NormalizedMerchantResult(
                    canonical_key=rule.canonical_key,
                    normalized_name=rule.display_name,
                    raw_pattern=primary_raw[:255] if primary_raw else rule.display_name,
                    normalized_token=cleaned_token[:150],
                    known_default_category=rule.default_category,
                )

    cleaned = _clean_token(primary_raw)
    if not cleaned:
        cleaned = _clean_token(raw_text or "")
    if not cleaned:
        return NormalizedMerchantResult(
            canonical_key="unknown_merchant",
            normalized_name="Unknown Merchant",
            raw_pattern=(primary_raw or "Unknown")[:255],
            normalized_token="unknown",
            known_default_category=None,
        )

    words = [w for w in cleaned.split() if len(w) > 1 or w.isalnum()][:4]
    canonical_key = "_".join(words).lower()[:120] or "unknown_merchant"
    display_name = " ".join(w.upper() if len(w) <= 3 and w.isalpha() else w.capitalize() for w in words)[:150]
    return NormalizedMerchantResult(
        canonical_key=canonical_key,
        normalized_name=display_name,
        raw_pattern=(primary_raw or display_name)[:255],
        normalized_token=cleaned[:150],
        known_default_category=None,
    )


def _clean_token(text: str) -> str:
    s = text.strip()
    if not s:
        return ""
    # Replace common delimiters with space
    s = re.sub(r"[/\\|_*:#,;()\[\]]+", " ", s)
    for pat in _NOISE_PATTERNS:
        s = pat.sub(" ", s)
    s = re.sub(r"[^A-Za-z0-9&'\s-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.lower()


def resolve_or_upsert_merchant(
    db: Session,
    repo: IntelligenceRepository,
    user_id: uuid.UUID,
    *,
    description: str | None,
    merchant_payee: str | None,
    amount: Decimal,
    tx_type: str,
    categories_by_name: dict[str, FinancialCategory],
) -> tuple[MerchantIdentity, NormalizedMerchantResult]:
    """
    Find existing alias/merchant for this user or create canonical MerchantIdentity + MerchantAlias.
    Never modifies a merchant whose normalized_name was explicitly confirmed by the user.
    """
    parsed = normalize_merchant_text(description, merchant_payee)

    # First check raw pattern alias if exact string exists for user
    alias = repo.get_alias_by_pattern(db, user_id, parsed.raw_pattern)
    if alias is not None:
        merchant = repo.get_merchant_by_id(db, user_id, alias.merchant_id)
        if merchant is not None:
            alias.occurrence_count += 1
            merchant.transaction_count += 1
            if tx_type == "expense":
                merchant.total_spent = (merchant.total_spent or Decimal("0.00")) + amount
            db.add(alias)
            db.add(merchant)
            return merchant, parsed

    # Next check canonical_key
    merchant = repo.get_merchant_by_key(db, user_id, parsed.canonical_key)
    if merchant is None:
        default_cat = (
            categories_by_name.get(parsed.known_default_category.lower())
            if parsed.known_default_category
            else None
        )
        merchant = MerchantIdentity(
            user_id=user_id,
            canonical_key=parsed.canonical_key,
            normalized_name=parsed.normalized_name,
            default_category_id=default_cat.id if default_cat else None,
            default_category_name=default_cat.name if default_cat else parsed.known_default_category,
            is_user_confirmed=False,
            transaction_count=1,
            total_spent=amount if tx_type == "expense" else Decimal("0.00"),
        )
        db.add(merchant)
        db.flush()
    else:
        merchant.transaction_count += 1
        if tx_type == "expense":
            merchant.total_spent = (merchant.total_spent or Decimal("0.00")) + amount
        db.add(merchant)

    # Record alias for raw pattern
    if parsed.raw_pattern:
        new_alias = MerchantAlias(
            user_id=user_id,
            merchant_id=merchant.id,
            raw_pattern=parsed.raw_pattern,
            normalized_token=parsed.normalized_token,
            occurrence_count=1,
        )
        db.add(new_alias)
        db.flush()

    return merchant, parsed
