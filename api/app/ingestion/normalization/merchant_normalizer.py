import re

# Known payment-processor / POS prefixes that precede the real merchant name.
_PREFIX_PATTERNS = [
    re.compile(r"^(SQ|TST|PAYPAL|PY|POS DEBIT|POS PURCHASE|ACH)\s*[\*:]?\s*", re.IGNORECASE),
]

# Trailing noise: transaction IDs, store numbers, reference codes, extra whitespace.
_TRAILING_ID_PATTERN = re.compile(r"[\*#]?\d{4,}$")
_TRAILING_STATE_CODE_PATTERN = re.compile(r"\s+[A-Z]{2}$")
_MULTI_SPACE_PATTERN = re.compile(r"\s{2,}")

# Canonical overrides for well-known merchants whose raw strings vary a lot.
_KNOWN_MERCHANTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"AMAZON", re.IGNORECASE), "Amazon"),
    (re.compile(r"WAL-?MART", re.IGNORECASE), "Walmart"),
    (re.compile(r"UBER\s*(EATS)?", re.IGNORECASE), "Uber"),
    (re.compile(r"STARBUCKS", re.IGNORECASE), "Starbucks"),
    (re.compile(r"NETFLIX", re.IGNORECASE), "Netflix"),
    (re.compile(r"SPOTIFY", re.IGNORECASE), "Spotify"),
    (re.compile(r"WHOLEFDS|WHOLE\s*FOODS", re.IGNORECASE), "Whole Foods"),
    (re.compile(r"TARGET", re.IGNORECASE), "Target"),
]


def normalize_merchant(raw: str) -> str:
    """Rule-based merchant cleanup (regex only in M1 — an ML-based normalizer
    is out of scope until a later milestone)."""
    value = raw.strip()
    if not value:
        return value

    for known_pattern, canonical in _KNOWN_MERCHANTS:
        if known_pattern.search(value):
            return canonical

    for prefix_pattern in _PREFIX_PATTERNS:
        value = prefix_pattern.sub("", value)

    value = _TRAILING_ID_PATTERN.sub("", value)
    value = _TRAILING_STATE_CODE_PATTERN.sub("", value)
    value = _MULTI_SPACE_PATTERN.sub(" ", value).strip(" -*#")

    return value.title() if value else raw.strip()
