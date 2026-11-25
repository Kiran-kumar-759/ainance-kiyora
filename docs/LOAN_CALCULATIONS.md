# Phase 6 — EMI, Amortization & Prepayment Calculation Methodology

Implemented cleanly with Python `Decimal` (`prec = 28` intermediate context, `ROUND_HALF_UP` quantized to `₹0.01`) in `backend/app/services/loans/emi_engine.py`. Binary floating-point is never used for authoritative loan math.

## 1. Periodic EMI Formulas

Let $P$ = outstanding principal, $R$ = annual interest rate (%), $n$ = remaining installments, and $k$ = periods per year (`12` monthly, `4` quarterly, `52` weekly).

- **Reducing Balance (`reducing_balance`, $R > 0$):**
  $$r = \frac{R}{100 \cdot k}, \qquad \text{EMI} = \text{round}_{0.01}\!\left(P \cdot r \cdot \frac{(1 + r)^n}{(1 + r)^n - 1}\right)$$
- **Flat Rate (`flat_rate`):**
  $$\text{Total Interest} = \text{round}_{0.01}\!\left(P \cdot \frac{R}{100} \cdot \frac{n}{k}\right), \qquad \text{EMI} = \text{round}_{0.01}\!\left(\frac{P + \text{Total Interest}}{n}\right)$$
- **Zero Interest (`zero_interest` or $R = 0$):**
  $$\text{Total Interest} = 0.00, \qquad \text{EMI} = \text{round}_{0.01}\!\left(\frac{P}{n}\right)$$

## 2. Amortization Schedule Reconciliation Rules

For each installment $i = 1 \dots n$:
1. Periodic interest $I_i = \text{round}_{0.01}(\text{Opening}_i \cdot r)$ (reducing balance), or flat periodic interest, or `0.00` (zero interest).
2. Calendar due dates advance via `advance_due_date` preserving `anchor_day` across month-ends (`31st`, `30th`) and leap years (`29 Feb`).
3. On intermediate periods ($i < n$), principal reduction is $\max(0, \text{EMI} - I_i)$ capped at $\text{Opening}_i$ so closing principal never becomes negative.
4. On the final installment ($i = n$), `Principal_n = Opening_n` and `EMI_n = Opening_n + I_n` (`is_final_adjustment = True` if adjusted by rounding residual), guaranteeing exact reconciliation:
   $$\sum_{i=1}^{n} \text{Principal}_i = P \quad \text{and} \quad \text{Closing}_n = ₹0.00.$$

## 3. Prepayment Simulation (`simulate_prepayment_scenario`)

Compares the remaining baseline schedule against a hypothetical lump-sum reduction (`lump_sum_prepayment`) and/or extra periodic payment (`extra_monthly_emi`) under `reduce_tenure` (EMI unchanged, solve remaining periods until principal hits `0.00`) or `reduce_emi` (re-solve periodic EMI over remaining tenure). Prepayment charges are included **only** when explicitly supplied via `user_prepayment_fee`.
