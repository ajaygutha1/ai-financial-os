import re

# Deliberately narrow: not every "ACH DEBIT" is a transfer (many are bill
# payments), so this only fires on unambiguous transfer language. It's a
# fallback for when transfer_detector's exact cross-account match can't run
# -- e.g. the other side of the transfer is at an external institution not
# connected to this system, so there's no counterpart row to match against.
_WIRE_TRANSFER_PATTERN = re.compile(r"\bWIRE\s*(TRANSFER|XFER)?\b|\bFEDWIRE\b", re.IGNORECASE)
_ACH_TRANSFER_PATTERN = re.compile(r"\bACH\s*(TRANSFER|XFER)\b", re.IGNORECASE)


def classify_payment_channel(description: str) -> str | None:
    """Returns 'wire', 'ach', or None. Pure text classifier, no DB access --
    same rule-based style as merchant_normalizer.py."""
    if _WIRE_TRANSFER_PATTERN.search(description):
        return "wire"
    if _ACH_TRANSFER_PATTERN.search(description):
        return "ach"
    return None
