import datetime as dt
from decimal import Decimal
from typing import Any

from app.providers.banking.base import BankingProvider
from app.schemas.finance.banking import BankingProviderInfo, DiscoveredAccountInfo

DEMO_INSTITUTIONS: dict[str, dict[str, Any]] = {
    "demo_national_bank": {
        "provider_id": "demo_national_bank",
        "name": "Demo National Bank of India",
        "description": "Simulated public sector bank offering savings and fixed deposits.",
        "logo_key": "building-2",
        "supported_account_types": ["savings", "current"],
        "accounts": [
            {
                "external_account_id": "dnb_sav_001",
                "name": "DNB Salary Savings Account",
                "account_type": "savings",
                "masked_account_number": "••• 4892",
                "balance": Decimal("125450.00"),
                "currency": "INR",
            },
            {
                "external_account_id": "dnb_cur_002",
                "name": "DNB Business Current Account",
                "account_type": "current",
                "masked_account_number": "••• 9912",
                "balance": Decimal("48500.00"),
                "currency": "INR",
            },
        ],
        "transactions": {
            "dnb_sav_001": [
                {
                    "external_reference": "dnb_tx_101",
                    "transaction_type": "income",
                    "amount": Decimal("85000.00"),
                    "category_name": "Salary",
                    "description": "Monthly Salary Credit - Tech Corp India",
                    "merchant_payee": "Tech Corp India Ltd",
                    "days_ago": 25,
                },
                {
                    "external_reference": "dnb_tx_102",
                    "transaction_type": "expense",
                    "amount": Decimal("18500.00"),
                    "category_name": "Housing & Rent",
                    "description": "House Rent Transfer for Month",
                    "merchant_payee": "Landlord",
                    "days_ago": 23,
                },
                {
                    "external_reference": "dnb_tx_103",
                    "transaction_type": "expense",
                    "amount": Decimal("3200.00"),
                    "category_name": "Utilities & Bills",
                    "description": "Electricity Bill Payment - BESCOM",
                    "merchant_payee": "BESCOM",
                    "days_ago": 15,
                },
                {
                    "external_reference": "dnb_tx_104",
                    "transaction_type": "expense",
                    "amount": Decimal("4650.00"),
                    "category_name": "Groceries",
                    "description": "Supermarket Grocery Order - BigBasket",
                    "merchant_payee": "BigBasket",
                    "days_ago": 10,
                },
            ],
            "dnb_cur_002": [
                {
                    "external_reference": "dnb_cur_tx_201",
                    "transaction_type": "income",
                    "amount": Decimal("35000.00"),
                    "category_name": "Freelance",
                    "description": "Client Consulting Retainer",
                    "merchant_payee": "Nexus Advisory",
                    "days_ago": 18,
                },
            ],
        },
    },
    "demo_private_bank": {
        "provider_id": "demo_private_bank",
        "name": "Demo Private Bank",
        "description": "Simulated leading private bank offering premium savings and credit cards.",
        "logo_key": "landmark",
        "supported_account_types": ["savings", "credit_card"],
        "accounts": [
            {
                "external_account_id": "dpb_sav_101",
                "name": "DPB Wealth Advantage Savings",
                "account_type": "savings",
                "masked_account_number": "••• 7183",
                "balance": Decimal("75000.00"),
                "currency": "INR",
            },
            {
                "external_account_id": "dpb_cc_102",
                "name": "DPB Millennia Titanium Credit Card",
                "account_type": "credit_card",
                "masked_account_number": "•••• 3481",
                "balance": Decimal("14250.00"),  # Outstanding liability
                "currency": "INR",
            },
        ],
        "transactions": {
            "dpb_sav_101": [
                {
                    "external_reference": "dpb_tx_301",
                    "transaction_type": "income",
                    "amount": Decimal("12000.00"),
                    "category_name": "Investments / Interest",
                    "description": "Mutual Fund Quarterly Dividend Credit",
                    "merchant_payee": "HDFC Mutual Fund",
                    "days_ago": 20,
                },
            ],
            "dpb_cc_102": [
                {
                    "external_reference": "dpb_cc_tx_401",
                    "transaction_type": "expense",
                    "amount": Decimal("6499.00"),
                    "category_name": "Shopping",
                    "description": "Online Electronics Order - Amazon India",
                    "merchant_payee": "Amazon India",
                    "days_ago": 8,
                },
                {
                    "external_reference": "dpb_cc_tx_402",
                    "transaction_type": "expense",
                    "amount": Decimal("1850.00"),
                    "category_name": "Food & Dining",
                    "description": "Dinner at Olive Bistro",
                    "merchant_payee": "Olive Bistro",
                    "days_ago": 5,
                },
                {
                    "external_reference": "dpb_cc_tx_403",
                    "transaction_type": "expense",
                    "amount": Decimal("1299.00"),
                    "category_name": "Entertainment",
                    "description": "Movie & Popcorn - PVR Inox",
                    "merchant_payee": "PVR Inox",
                    "days_ago": 2,
                },
            ],
        },
    },
    "demo_digital_bank": {
        "provider_id": "demo_digital_bank",
        "name": "Demo Digital Neobank",
        "description": "Simulated app-first neobank with digital wallet and instant UPI support.",
        "logo_key": "smartphone",
        "supported_account_types": ["digital_wallet", "savings"],
        "accounts": [
            {
                "external_account_id": "ddb_wal_201",
                "name": "Demo Digital UPI Wallet",
                "account_type": "digital_wallet",
                "masked_account_number": "••• 6204",
                "balance": Decimal("4850.00"),
                "currency": "INR",
            },
        ],
        "transactions": {
            "ddb_wal_201": [
                {
                    "external_reference": "ddb_tx_501",
                    "transaction_type": "expense",
                    "amount": Decimal("340.00"),
                    "category_name": "Transportation",
                    "description": "Auto Ride via Namma Yatri UPI",
                    "merchant_payee": "Namma Yatri",
                    "days_ago": 3,
                },
                {
                    "external_reference": "ddb_tx_502",
                    "transaction_type": "expense",
                    "amount": Decimal("480.00"),
                    "category_name": "Food & Dining",
                    "description": "Coffee & Snacks - Third Wave Coffee",
                    "merchant_payee": "Third Wave Coffee",
                    "days_ago": 1,
                },
            ],
        },
    },
}


class DemoBankingProvider(BankingProvider):
    """Implementation of simulated Indian banking institutions for safe demonstration."""

    def __init__(self, provider_id: str):
        if provider_id not in DEMO_INSTITUTIONS:
            raise ValueError(f"Unknown demo provider: {provider_id}")
        self.provider_id = provider_id
        self.data = DEMO_INSTITUTIONS[provider_id]

    def get_info(self) -> BankingProviderInfo:
        return BankingProviderInfo(
            provider_id=self.data["provider_id"],
            name=self.data["name"],
            description=self.data["description"],
            is_simulated=True,
            logo_key=self.data["logo_key"],
            supported_account_types=self.data["supported_account_types"],
        )

    def discover_accounts(self, connection_id: str, user_id: str) -> list[DiscoveredAccountInfo]:
        results = []
        for acc in self.data["accounts"]:
            results.append(
                DiscoveredAccountInfo(
                    external_account_id=acc["external_account_id"],
                    name=acc["name"],
                    account_type=acc["account_type"],
                    institution_name=self.data["name"],
                    masked_account_number=acc["masked_account_number"],
                    balance=acc["balance"],
                    currency=acc["currency"],
                )
            )
        return results

    def fetch_transactions(
        self,
        connection_id: str,
        account_external_id: str,
    ) -> list[dict[str, Any]]:
        raw_txs = self.data.get("transactions", {}).get(account_external_id, [])
        today = dt.date.today()
        result = []
        for tx in raw_txs:
            tx_date = today - dt.timedelta(days=tx["days_ago"])
            result.append(
                {
                    "external_reference": tx["external_reference"],
                    "transaction_type": tx["transaction_type"],
                    "amount": tx["amount"],
                    "category_name": tx["category_name"],
                    "description": tx["description"],
                    "merchant_payee": tx["merchant_payee"],
                    "transaction_date": tx_date,
                    "notes": f"Simulated record from {self.data['name']}",
                }
            )
        return result


def get_all_demo_providers() -> list[BankingProviderInfo]:
    return [DemoBankingProvider(pid).get_info() for pid in DEMO_INSTITUTIONS]


def get_demo_provider(provider_id: str) -> DemoBankingProvider:
    return DemoBankingProvider(provider_id)
