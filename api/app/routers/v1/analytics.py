from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics.modules import (
    anomaly_detection,
    budget_vs_actual,
    burn_rate,
    cash_flow,
    debt_payoff,
    emergency_fund,
    expense_trends,
    net_worth,
    ratios,
    retirement_contributions,
    savings_rate,
    subscriptions,
    taxable_events,
)
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.analytics import (
    AnomalyDetectionResponse,
    BudgetVsActualResponse,
    BurnRateResponse,
    CashFlowResponse,
    DebtPayoffResponse,
    EmergencyFundResponse,
    ExpenseTrendsResponse,
    NetWorthResponse,
    RatiosResponse,
    RetirementContributionsResponse,
    SavingsRateResponse,
    SubscriptionsResponse,
    TaxableEventsResponse,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/net-worth", response_model=NetWorthResponse)
def get_net_worth(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> NetWorthResponse:
    return net_worth.compute(db, current_user.id)


@router.get("/cash-flow", response_model=CashFlowResponse)
def get_cash_flow(
    months: int = Query(default=cash_flow.DEFAULT_MONTHS, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CashFlowResponse:
    return cash_flow.compute(db, current_user.id, months=months)


@router.get("/burn-rate", response_model=BurnRateResponse)
def get_burn_rate(
    months: int = Query(default=burn_rate.DEFAULT_MONTHS, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BurnRateResponse:
    return burn_rate.compute(db, current_user.id, months=months)


@router.get("/savings-rate", response_model=SavingsRateResponse)
def get_savings_rate(
    months: int = Query(default=savings_rate.DEFAULT_MONTHS, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SavingsRateResponse:
    return savings_rate.compute(db, current_user.id, months=months)


@router.get("/expense-trends", response_model=ExpenseTrendsResponse)
def get_expense_trends(
    months: int = Query(default=expense_trends.DEFAULT_MONTHS, ge=2, le=24),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExpenseTrendsResponse:
    return expense_trends.compute(db, current_user.id, months=months)


@router.get("/subscriptions", response_model=SubscriptionsResponse)
def get_subscriptions(
    months: int = Query(default=subscriptions.DEFAULT_MONTHS, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionsResponse:
    return subscriptions.compute(db, current_user.id, months=months)


@router.get("/emergency-fund", response_model=EmergencyFundResponse)
def get_emergency_fund(
    months: int = Query(default=emergency_fund.DEFAULT_MONTHS, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmergencyFundResponse:
    return emergency_fund.compute(db, current_user.id, months=months)


@router.get("/debt-payoff", response_model=DebtPayoffResponse)
def get_debt_payoff(
    months: int = Query(default=debt_payoff.DEFAULT_MONTHS, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DebtPayoffResponse:
    return debt_payoff.compute(db, current_user.id, months=months)


@router.get("/ratios", response_model=RatiosResponse)
def get_ratios(
    months: int = Query(default=ratios.DEFAULT_MONTHS, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RatiosResponse:
    return ratios.compute(db, current_user.id, months=months)


@router.get("/retirement-contributions", response_model=RetirementContributionsResponse)
def get_retirement_contributions(
    months: int = Query(default=retirement_contributions.DEFAULT_MONTHS, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RetirementContributionsResponse:
    return retirement_contributions.compute(db, current_user.id, months=months)


@router.get("/taxable-events", response_model=TaxableEventsResponse)
def get_taxable_events(
    months: int = Query(default=taxable_events.DEFAULT_MONTHS, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxableEventsResponse:
    return taxable_events.compute(db, current_user.id, months=months)


@router.get("/anomaly-detection", response_model=AnomalyDetectionResponse)
def get_anomaly_detection(
    months: int = Query(default=anomaly_detection.DEFAULT_MONTHS, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnomalyDetectionResponse:
    return anomaly_detection.compute(db, current_user.id, months=months)


@router.get("/budget-vs-actual", response_model=BudgetVsActualResponse)
def get_budget_vs_actual(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> BudgetVsActualResponse:
    return budget_vs_actual.compute(db, current_user.id)
