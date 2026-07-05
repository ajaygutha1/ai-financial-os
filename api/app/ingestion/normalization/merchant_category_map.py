# Hand-authored default category for the known-merchant overrides in
# merchant_normalizer.py. Deliberately small and explicit rather than a
# general classification engine -- that's a later milestone's job (M6's
# Expense Analyst / Budget Coach agents). Unmapped merchants stay
# uncategorized (category_id=None) rather than guessing.
KNOWN_MERCHANT_CATEGORIES: dict[str, str] = {
    "Amazon": "Shopping",
    "Walmart": "Shopping",
    "Target": "Shopping",
    "Uber": "Transportation",
    "Starbucks": "Food & Dining",
    "Netflix": "Entertainment",
    "Spotify": "Entertainment",
    "Whole Foods": "Groceries",
}
