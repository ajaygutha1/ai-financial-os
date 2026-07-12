from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class NetWorthResponse(BaseModel):
    net_worth: Decimal
    assets_total: Decimal
    liabilities_total: Decimal
    by_account_type: dict[str, Decimal]
    methodology: str


class CashFlowMonth(BaseModel):
    month: date
    income: Decimal
    expenses: Decimal
    net: Decimal
    transaction_count: int


class CashFlowResponse(BaseModel):
    months: list[CashFlowMonth]
    total_income: Decimal
    total_expenses: Decimal
    net: Decimal
    period_start: date
    period_end: date
    methodology: str


class BurnRateResponse(BaseModel):
    average_monthly_burn: Decimal
    is_burning: bool
    months_considered: int
    period_start: date
    period_end: date
    methodology: str


class SavingsRateMonth(BaseModel):
    month: date
    income: Decimal
    expenses: Decimal
    savings_rate: Decimal | None


class SavingsRateResponse(BaseModel):
    months: list[SavingsRateMonth]
    average_savings_rate: Decimal | None
    months_with_income: int
    period_start: date
    period_end: date
    methodology: str


class CategoryTrend(BaseModel):
    category: str
    latest_month_total: Decimal
    prior_average: Decimal
    change_pct: Decimal | None
    trend: str  # "rising" | "falling" | "steady" | "new"


class ExpenseTrendsResponse(BaseModel):
    categories: list[CategoryTrend]
    period_start: date
    period_end: date
    methodology: str


class DetectedSubscription(BaseModel):
    merchant: str
    cadence: str  # "weekly" | "monthly" | "annual"
    average_amount: Decimal
    occurrences: int
    last_charge_date: date
    next_expected_date: date


class SubscriptionsResponse(BaseModel):
    subscriptions: list[DetectedSubscription]
    estimated_monthly_total: Decimal
    period_start: date
    period_end: date
    methodology: str


class EmergencyFundResponse(BaseModel):
    liquid_assets: Decimal
    average_monthly_expenses: Decimal
    months_of_coverage: Decimal | None
    health_tier: str  # "unknown" | "critical" | "low" | "adequate" | "strong"
    methodology: str


class DebtAccountProjection(BaseModel):
    account_id: UUID
    account_name: str
    current_balance: Decimal
    net_monthly_paydown: Decimal
    months_to_payoff: Decimal | None
    on_track: bool


class DebtPayoffResponse(BaseModel):
    accounts: list[DebtAccountProjection]
    months_considered: int
    methodology: str


class RatiosResponse(BaseModel):
    savings_rate: Decimal | None
    expense_to_income_ratio: Decimal | None
    liquidity_ratio_months: Decimal | None
    debt_to_annual_income: Decimal | None
    months_considered: int
    methodology: str
