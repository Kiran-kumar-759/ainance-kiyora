# Banking Integration Architecture & Simulated Demo Provider

**Project:** AI Personal Finance Manager — India  
**Phase:** Phase 2  
**Provider Mode:** Provider-Independent Adapter (Simulated Sandbox)

---

## 1. Architectural Strategy

The banking module utilizes a provider-independent adapter pattern to decouple core financial accounting from external banking APIs:

```
[UI Banking Page]
        ↓
[API Routes: /api/v1/banking/*]
        ↓
[BankingService & BankingRepository]
        ↓
[BankingProvider Interface]
        ↓
┌─────────────────────────────────┬─────────────────────────────────┐
│ Current: DemoBankingProvider    │ Future: RBI Account Aggregator  │
│ (In-memory deterministic mocks) │ (Finvu, Setu, Anumati - AA API) │
└─────────────────────────────────┴─────────────────────────────────┘
```

This decoupled design ensures that when real Indian Account Aggregator (AA) integrations are introduced in future stages, the financial account, transaction, and double-entry ledger models remain completely untouched.

---

## 2. Simulated Indian Institutions

Phase 2 provides 3 realistic fictional Indian banking institutions:

### 2.1 Demo National Bank of India (`demo_national_bank`)
- **Institution Profile:** Simulated large public sector bank (PSU).
- **Accounts:**
  - DNB Salary Savings Account (`••• 4892`, ₹1,25,450.00)
  - DNB Business Current Account (`••• 9912`, ₹48,500.00)
- **Sample Transactions:** Salary credit from Tech Corp India, House rent payment to landlord, BESCOM electricity bill payment, BigBasket grocery delivery, Client retainer.

### 2.2 Demo Private Bank (`demo_private_bank`)
- **Institution Profile:** Simulated leading corporate private bank.
- **Accounts:**
  - DPB Wealth Advantage Savings (`••• 7183`, ₹75,000.00)
  - DPB Millennia Titanium Credit Card (`•••• 3481`, ₹14,250.00 outstanding debt)
- **Sample Transactions:** Mutual fund dividend credit, Amazon India online order, Olive Bistro dining, PVR Inox cinema.

### 2.3 Demo Digital Neobank (`demo_digital_bank`)
- **Institution Profile:** Simulated app-first fintech neobank with instant UPI.
- **Accounts:**
  - Demo Digital UPI Wallet (`••• 6204`, ₹4,850.00)
- **Sample Transactions:** Namma Yatri auto ride, Third Wave Coffee.

---

## 3. End-to-End User Journey & Consent

1. **Provider Listing:** User navigates to the Simulated Banking tab and views available institutions with clear disclaimers that this is a simulated sandbox.
2. **Explicit Consent:** Connecting requires checking an explicit consent checkbox. Unconsented requests fail with HTTP 400.
3. **Account Discovery:** `GET /api/v1/banking/connections/{id}/accounts` queries the provider. Previously imported accounts are marked `already_imported = true`.
4. **Selective Import:** User selects specific discovered accounts to import into `financial_accounts` with `source = 'demo_bank'`.
5. **Idempotent Synchronization:**
   - Synchronizing queries provider transactions.
   - Provider records carry an immutable `external_reference` (e.g. `dnb_tx_101`).
   - The sync engine checks `transaction_repo.get_by_external_reference(user_id, account_id, external_ref)`.
   - Existing transactions are skipped.
   - Multiple sync clicks create **zero duplicate records**.
6. **Disconnection:** User can disconnect anytime. Existing imported accounts and transactions are preserved in the ledger.

---

## 4. Absolute Security & Credential Rules

1. **No Real Banking Credentials:** The system **never** prompts for, receives, or stores Internet Banking passwords, ATM PINs, UPI PINs, CVVs, or OTPs.
2. **No Live Network Access:** Demo provider data is generated deterministically in-process from backend fixtures.
3. **Audit Trails:** Each synchronization run is recorded in `banking_sync_runs` with timestamps and accounts/transactions counts.
