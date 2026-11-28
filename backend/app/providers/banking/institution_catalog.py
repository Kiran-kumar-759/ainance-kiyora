from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.providers.banking.demo_provider import DEMO_INSTITUTIONS


@dataclass(frozen=True)
class BankInstitutionEntry:
    """Catalog metadata describing an Indian financial institution or explicit demo bank."""

    bank_id: str
    bank_name: str
    short_name: str
    bank_code: str
    category: str  # public_sector, private_sector, neobank, demo
    logo_key: str
    logo_url: str
    supported_connection_methods: tuple[str, ...]
    provider_id: str
    provider_available: bool
    live_supported: bool
    is_demo: bool
    connection_availability_status: str  # demo_only, live_unavailable, available
    description: str
    unavailable_reason: str | None = None


def _build_catalog() -> list[BankInstitutionEntry]:
    live_aa_configured = bool(getattr(settings, "ACCOUNT_AGGREGATOR_ENABLED", False))
    real_methods: tuple[str, ...] = (
        ("account_aggregator", "statement_import", "manual_account")
        if live_aa_configured
        else ("statement_import", "manual_account")
    )
    real_status = "available" if live_aa_configured else "live_unavailable"
    real_reason = (
        None
        if live_aa_configured
        else "Live RBI Account Aggregator / FIP gateway is not configured in this environment. Use CSV/XLSX statement import, manual account creation, or Demo Banking."
    )

    real_banks = [
        ("state_bank_of_india", "State Bank of India", "SBI", "SBIN", "public_sector", "sbi"),
        ("hdfc_bank", "HDFC Bank", "HDFC", "HDFC", "private_sector", "hdfc"),
        ("icici_bank", "ICICI Bank", "ICICI", "ICIC", "private_sector", "icici"),
        ("axis_bank", "Axis Bank", "Axis", "UTIB", "private_sector", "axis"),
        ("kotak_mahindra_bank", "Kotak Mahindra Bank", "Kotak", "KKBK", "private_sector", "kotak"),
        ("punjab_national_bank", "Punjab National Bank", "PNB", "PUNB", "public_sector", "pnb"),
        ("bank_of_baroda", "Bank of Baroda", "BoB", "BARB", "public_sector", "bob"),
        ("canara_bank", "Canara Bank", "Canara", "CNRB", "public_sector", "canara"),
        ("union_bank_of_india", "Union Bank of India", "Union Bank", "UBIN", "public_sector", "union_bank"),
        ("idfc_first_bank", "IDFC FIRST Bank", "IDFC FIRST", "IDFB", "private_sector", "idfc_first"),
        ("indusind_bank", "IndusInd Bank", "IndusInd", "INDB", "private_sector", "indusind"),
        ("yes_bank", "Yes Bank", "Yes Bank", "YESB", "private_sector", "yes_bank"),
    ]

    entries: list[BankInstitutionEntry] = [
        BankInstitutionEntry(
            bank_id=bank_id,
            bank_name=bank_name,
            short_name=short_name,
            bank_code=bank_code,
            category=category,
            logo_key=logo_key,
            logo_url=f"/assets/banks/{logo_key}.svg",
            supported_connection_methods=real_methods,
            provider_id="account_aggregator",
            provider_available=live_aa_configured,
            live_supported=live_aa_configured,
            is_demo=False,
            connection_availability_status=real_status,
            description=f"{bank_name} ({bank_code}) — supports statement import and manual account tracking.",
            unavailable_reason=real_reason,
        )
        for bank_id, bank_name, short_name, bank_code, category, logo_key in real_banks
    ]

    for prov_id, info in DEMO_INSTITUTIONS.items():
        entries.append(
            BankInstitutionEntry(
                bank_id=prov_id,
                bank_name=info["name"],
                short_name=info["name"],
                bank_code=prov_id.upper(),
                category="demo",
                logo_key=info["logo_key"],
                logo_url=f"/assets/banks/{prov_id}.svg",
                supported_connection_methods=("demo",),
                provider_id=prov_id,
                provider_available=True,
                live_supported=False,
                is_demo=True,
                connection_availability_status="demo_only",
                description=info["description"],
                unavailable_reason=None,
            )
        )

    return entries


def list_bank_institutions(
    *,
    search: str | None = None,
    method: str | None = None,
    category: str | None = None,
    include_demo: bool = True,
) -> list[BankInstitutionEntry]:
    """Lists configured and cataloged Indian financial institutions with optional filtering."""
    items = _build_catalog()
    if not include_demo:
        items = [entry for entry in items if not entry.is_demo]
    if category:
        cat_clean = category.strip().lower()
        items = [entry for entry in items if entry.category.lower() == cat_clean]
    if method:
        method_clean = method.strip().lower()
        items = [
            entry
            for entry in items
            if method_clean in [m.lower() for m in entry.supported_connection_methods]
        ]
    if search and search.strip():
        q = search.strip().lower()
        items = [
            entry
            for entry in items
            if q in entry.bank_name.lower()
            or q in entry.short_name.lower()
            or q in entry.bank_code.lower()
            or q in entry.bank_id.lower()
        ]
    return items


def get_bank_institution(bank_id: str) -> BankInstitutionEntry | None:
    """Looks up an institution entry by catalog bank_id or demo provider_id."""
    clean = bank_id.strip().lower()
    for entry in _build_catalog():
        if entry.bank_id.lower() == clean or entry.provider_id.lower() == clean:
            return entry
    return None
