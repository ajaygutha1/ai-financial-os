from decimal import Decimal

from pydantic import BaseModel


class NetWorthResponse(BaseModel):
    net_worth: Decimal
    assets_total: Decimal
    liabilities_total: Decimal
    by_account_type: dict[str, Decimal]
