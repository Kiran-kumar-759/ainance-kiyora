from abc import ABC, abstractmethod
from typing import Any

from app.schemas.finance.banking import BankingProviderInfo, DiscoveredAccountInfo


class BankingProvider(ABC):
    """Abstract interface defining the contract for banking providers (simulated or real)."""

    @abstractmethod
    def get_info(self) -> BankingProviderInfo:
        """Returns metadata describing the institution, features, and simulation notice."""
        pass

    @abstractmethod
    def discover_accounts(self, connection_id: str, user_id: str) -> list[DiscoveredAccountInfo]:
        """Discovers available accounts associated with the connection."""
        pass

    @abstractmethod
    def fetch_transactions(
        self,
        connection_id: str,
        account_external_id: str,
    ) -> list[dict[str, Any]]:
        """
        Fetches deterministic transactions for synchronization.
        Each transaction includes an immutable external_id for idempotency.
        """
        pass
