from decimal import Decimal

# Static rate table (quoted as 1 unit of the key currency -> USD), pending a
# real FX-rate data source in a later milestone (M9, alongside real connector
# credentials). Deliberately conservative in scope: this never mutates a
# transaction's recorded amount/currency (the source of truth is what the
# connector/file actually reported) -- it only computes an informational
# converted value for provenance, which is what M3's analytics engine will
# eventually need for cross-currency aggregation.
_STATIC_RATES_TO_USD: dict[str, Decimal] = {
    "USD": Decimal("1"),
    "EUR": Decimal("1.08"),
    "GBP": Decimal("1.27"),
    "CAD": Decimal("0.73"),
    "JPY": Decimal("0.0067"),
}


def convert_to_account_currency(
    *, amount: Decimal, from_currency: str, to_currency: str
) -> Decimal | None:
    """Converts `amount` from `from_currency` to `to_currency` via USD as a
    pivot. Returns None (rather than guessing) if either currency has no
    known rate -- callers should treat that as "conversion unavailable," not
    as a zero-value conversion.
    """
    if from_currency == to_currency:
        return amount

    from_rate = _STATIC_RATES_TO_USD.get(from_currency)
    to_rate = _STATIC_RATES_TO_USD.get(to_currency)
    if from_rate is None or to_rate is None:
        return None

    usd_amount = amount * from_rate
    return usd_amount / to_rate
