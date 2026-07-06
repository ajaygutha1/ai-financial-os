import pytest
from sqlalchemy.orm import Session

from app.analytics.engine import AnalyticsEngine, UnknownMetricError
from app.models.user import User
from app.schemas.analytics import NetWorthResponse


def test_available_metrics_lists_all_modules(db_session: Session) -> None:
    engine = AnalyticsEngine(db_session)

    assert engine.available_metrics() == [
        "burn_rate",
        "cash_flow",
        "debt_payoff",
        "emergency_fund",
        "expense_trends",
        "net_worth",
        "ratios",
        "savings_rate",
        "subscriptions",
    ]


def test_run_dispatches_to_the_right_module(db_session: Session, test_user: User) -> None:
    engine = AnalyticsEngine(db_session)

    result = engine.run("net_worth", test_user.id)

    assert isinstance(result, NetWorthResponse)


def test_run_raises_on_unknown_metric(db_session: Session, test_user: User) -> None:
    engine = AnalyticsEngine(db_session)

    with pytest.raises(UnknownMetricError):
        engine.run("not_a_real_metric", test_user.id)
