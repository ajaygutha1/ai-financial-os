# Demo data

Two CSVs with ~6 months of realistic, date-relative transaction history, for
demoing Milestone 3's analytics dashboard end-to-end without needing real
Plaid/bank credentials. Regenerate any time with:

```bash
python docs/demo-data/generate.py
```

(dates are always computed relative to "today," so the files never go stale
-- rerun before a demo if it's been a while since they were last generated.)

## What's in them

- **checking.csv**: monthly salary (+$6,200), rent (-$1,850), utilities, a
  $45/mo gym membership, weekly Whole Foods groceries (amount varies on
  purpose, so it's *not* mistaken for a subscription), occasional Uber/
  Starbucks charges, a one-off $540 "Auto Repair Shop" spike three months
  back, and a monthly payment to the credit card.
- **credit_card.csv**: Netflix ($15.99/mo) and Spotify ($10.99/mo) --
  consistent amount and cadence, so the subscriptions detector should catch
  both -- plus Amazon purchases, an occasional restaurant charge, and a
  monthly payment that's set slightly above that month's charges (so debt
  payoff shows a healthy "on track" trend).

Merchant names are chosen to match the known-merchant table in
`app/ingestion/normalization/merchant_normalizer.py` (Whole Foods, Netflix,
Spotify, Uber, Starbucks, Amazon), so they get normalized *and*
auto-categorized (Groceries, Entertainment, Transportation, Food & Dining,
Shopping) via `merchant_category_map.py` -- the expense-trends and
subscriptions widgets have real categories/cadences to show, not just
"Uncategorized."

## Walkthrough

1. `docker compose up` (or confirm the stack is already running), then open
   http://localhost:3000 and register/log in.
2. **New account** → name "Checking", type Checking, current balance
   `9500`. Create it.
3. **New account** → name "Credit Card", type Credit Card, current balance
   `380`. Create it.

   (CSV import only adds transaction history -- it doesn't touch
   `current_balance` -- so these starting balances are set by hand once,
   same as a real user would when first connecting an account.)
4. **Import CSV** → account "Checking" → file `docs/demo-data/checking.csv`
   → leave "This file represents outflows as positive amounts" **unchecked**
   (the file already encodes the final sign convention: positive = money in,
   negative = money out) → Import.
5. **Import CSV** → account "Credit Card" → file
   `docs/demo-data/credit_card.csv` → leave the checkbox **unchecked** →
   Import.
6. Back on the dashboard, you should see:
   - **Net worth**: ~$9,120 (9,500 checking − 380 owed).
   - **Cash flow**: ~6 months of income vs. expenses, net trending positive.
   - **Emergency fund**: liquid assets vs. average monthly spend, with a
     health-tier badge.
   - **Financial ratios**: savings rate, burn/saving rate, debt-to-income,
     liquidity in months.
   - **Expense trends**: Groceries, Food & Dining, Transportation, Shopping,
     and the one-off Auto Repair spike, each with a rising/falling/steady
     indicator.
   - **Subscriptions**: Netflix and Spotify (and the gym membership from the
     checking account), each with detected monthly cadence and amount.
   - **Debt payoff**: the credit card projected as on-track, since payments
     were generated slightly ahead of that month's charges.
7. Re-upload either CSV to see duplicate detection flag every row instead of
   double-importing (Milestone 1/2 behavior, still intact).
