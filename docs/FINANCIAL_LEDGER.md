# Financial Ledger & Double-Entry Accounting Specification

**Project:** AI Personal Finance Manager — India  
**Phase:** Phase 2  
**Database:** PostgreSQL 18.6  
**Storage Precision:** `NUMERIC(19, 2)` & Python `Decimal`

---

## 1. Accounting Foundation

The AI Personal Finance Manager implements a double-entry bookkeeping engine. Account balances are never arbitrarily updated or computed on-the-fly with ad-hoc heuristics; rather, they are calculated authoritatively from active, unreversed double-entry journal postings in PostgreSQL.

Every posted financial journal satisfies the fundamental accounting identity:

$$\sum \text{Debits} = \sum \text{Credits}$$

---

## 2. Account Classification and Sign Conventions

The system categorizes user financial accounts into two core accounting classes:

### 2.1 Asset Accounts
- **Account Types:** `savings`, `current`, `cash`, `digital_wallet`, `other`
- **Debit Effect:** Increases asset balance (cash in).
- **Credit Effect:** Decreases asset balance (cash out).
- **Authoritative Balance Formula:**
  $$\text{Asset Balance} = \sum \text{Debits} - \sum \text{Credits}$$

### 2.2 Liability Accounts
- **Account Types:** `credit_card`
- **Credit Effect:** Increases outstanding liability (new card charge / debt).
- **Debit Effect:** Decreases outstanding liability (card payment / merchant refund).
- **Authoritative Balance Formula:**
  $$\text{Outstanding Liability} = \sum \text{Credits} - \sum \text{Debits}$$
  *Convention:* Displayed in the UI as a positive number representing the debt owed on the card.

---

## 3. Double-Entry Posting Rules

### 3.1 Opening Balances
Opening positions represent existing wealth or liabilities prior to system tracking, not newly earned income or expenses:
- **Asset Account with Positive Opening Balance ($B > 0$):**
  - **Debit:** Financial Account ($\text{amount} = B$)
  - **Credit:** Opening Balance Equity Offset ($\text{account\_id} = \text{NULL}$, $\text{amount} = B$)
- **Credit Card with Initial Debt ($L > 0$):**
  - **Credit:** Financial Account ($\text{amount} = L$)
  - **Debit:** Opening Balance Equity Offset ($\text{account\_id} = \text{NULL}$, $\text{amount} = L$)
- **Opening Balance Correction:** Marks prior opening journal `is_reversed = True`, creates a new balanced opening journal with corrected amounts, and triggers an atomic recalculation of the account balance.

### 3.2 Income Transactions
- **Asset Account (e.g. Salary into Savings):**
  - **Debit:** Asset Account (money in)
  - **Credit:** Nominal Income Counter-Account ($\text{account\_id} = \text{NULL}$)
- **Credit Card Account (e.g. Merchant Refund):**
  - **Debit:** Credit Card Account (reduces card liability)
  - **Credit:** Nominal Income/Refund Counter-Account ($\text{account\_id} = \text{NULL}$)

### 3.3 Expense Transactions
- **Asset Account (e.g. Groceries via Cash or Debit):**
  - **Debit:** Nominal Expense Counter-Account ($\text{account\_id} = \text{NULL}$)
  - **Credit:** Asset Account (money out)
- **Credit Card Account (e.g. Online Shopping):**
  - **Debit:** Nominal Expense Counter-Account ($\text{account\_id} = \text{NULL}$)
  - **Credit:** Credit Card Account (increases outstanding liability)

### 3.4 Transfers & Credit Card Bill Payments
Fund transfers move money atomically between two user accounts without generating artificial income or expense records:
- **Source Account (e.g. Savings):**
  - **Credit:** Source Account (money out)
- **Destination Account (e.g. Wallet or Current):**
  - **Debit:** Destination Account (money in)
- **Credit Card Bill Payment (Transfer from Savings to Credit Card):**
  - **Credit:** Savings Account (reduces bank balance)
  - **Debit:** Credit Card Account (reduces credit card liability)
  - **Result:** Perfectly balanced journal ($\text{Debits} = \text{Credits}$), leaving user net financial position unchanged while reducing both asset and liability.

---

## 4. Transfer & Transaction Reversals

1. Historical accounting entries are **never physically modified or destroyed** in the journal ledger.
2. When a transaction is edited (amount or date changed) or deleted, its active journal is marked `is_reversed = True`.
3. If deleted, the balance is recalculated directly from remaining active entries.
4. If edited, a replacement balanced journal is posted in the same database transaction.
5. Transfer reversals mark `status = 'reversed'` on the transfer record, mark the transfer journal `is_reversed = True`, record the reversal timestamp and reason, and atomically restore both account balances.

---

## 5. Monetary Integrity Constraints

- Database Column: `NUMERIC(19, 2)`
- Backend Type: Python `decimal.Decimal`
- No floating-point (`float` in Python or `number` calculations in JS) arithmetic is permitted in financial calculations.
- Transactions are checked at the API layer for `amount > 0`.
- All financial mutations are executed within atomic PostgreSQL transactions (`with db.begin():` or managed session transactions).
