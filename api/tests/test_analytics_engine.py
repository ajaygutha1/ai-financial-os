import pytest
from sqlalchemy.orm import Session

from app.analytics.engine import AnalyticsEngine, UnknownMetricError
from app.core.exceptions import ValidationError
from app.models.user import User
from app.schemas.analytics import NetWorthResponse


def test_available_metrics_lists_all_modules(db_session: Session) -> None:
    engine = AnalyticsEngine(db_session)

    assert engine.available_metrics() == [
        "anomaly_detection",
        "burn_rate",
        "cash_flow",
        "debt_payoff",
        "emergency_fund",
        "expense_trends",
        "net_worth",
        "ratios",
        "retirement_contributions",
        "savings_rate",
        "subscriptions",
        "taxable_events",
    ]


def test_run_dispatches_to_the_right_module(db_session: Session, test_user: User) -> None:
    engine = AnalyticsEngine(db_session)

    result = engine.run("net_worth", test_user.id)

    assert isinstance(result, NetWorthResponse)


def test_run_raises_on_unknown_metric(db_session: Session, test_user: User) -> None:
    engine = AnalyticsEngine(db_session)

    with pytest.raises(UnknownMetricError):
        engine.run("not_a_real_metric", test_user.id)


@pytest.mark.parametrize("months", [0, -1, 25, 1000])
def test_run_rejects_out_of_range_months(db_session: Session, test_user: User, months: int) -> None:
    # The AI tool-calling path (app/ai/tools/analytics_tools.py) calls
    # engine.run() directly, bypassing the router's Query(ge=1, le=24) --
    # this is the only remaining validation for a model-supplied months
    # value, and the modules themselves blow up with ZeroDivisionError/
    # IndexError on an empty date range if it's skipped.
    engine = AnalyticsEngine(db_session)

    with pytest.raises(ValidationError):
        engine.run("burn_rate", test_user.id, months=months)


def test_run_rejects_non_integer_months(db_session: Session, test_user: User) -> None:
    engine = AnalyticsEngine(db_session)

    with pytest.raises(ValidationError):
        engine.run("burn_rate", test_user.id, months="12")


def test_run_accepts_boundary_months(db_session: Session, test_user: User) -> None:
    engine = AnalyticsEngine(db_session)

    # Must not raise -- 1 and 24 are valid, inclusive boundaries.
    engine.run("burn_rate", test_user.id, months=1)
    engine.run("burn_rate", test_user.id, months=24)
