import uuid
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.analytics.modules import (
    burn_rate,
    cash_flow,
    debt_payoff,
    emergency_fund,
    expense_trends,
    net_worth,
    ratios,
    savings_rate,
    subscriptions,
)
from app.core.exceptions import ValidationError

_MIN_MONTHS = 1
_MAX_MONTHS = 24

ComputeFn = Callable[..., BaseModel]

_REGISTRY: dict[str, ComputeFn] = {
    "net_worth": net_worth.compute,
    "cash_flow": cash_flow.compute,
    "burn_rate": burn_rate.compute,
    "savings_rate": savings_rate.compute,
    "expense_trends": expense_trends.compute,
    "subscriptions": subscriptions.compute,
    "emergency_fund": emergency_fund.compute,
    "debt_payoff": debt_payoff.compute,
    "ratios": ratios.compute,
}


class UnknownMetricError(KeyError):
    pass


class AnalyticsEngine:
    """Registry of every analytics module, keyed by metric name. Routers call
    each module directly today for full static typing; this registry exists
    so Milestone 4's AI agents have one generic entry point -- `run()` -- to
    call any metric as a tool without needing to know each module's import
    path individually."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def available_metrics(self) -> list[str]:
        return sorted(_REGISTRY)

    def run(self, metric: str, user_id: uuid.UUID, **params: Any) -> BaseModel:
        compute_fn = _REGISTRY.get(metric)
        if compute_fn is None:
            raise UnknownMetricError(metric)
        # The FastAPI routers validate `months` via Query(ge=1, le=24), but
        # this is also the AI tool-calling entry point (see
        # app/ai/tools/analytics_tools.py) -- Anthropic tool schemas can't
        # express numeric min/max, so a model-supplied out-of-range value
        # reaches here unvalidated and would otherwise blow up as a raw
        # ZeroDivisionError/IndexError deep in a module.
        if "months" in params:
            months = params["months"]
            if (
                not isinstance(months, int)
                or isinstance(months, bool)
                or not (_MIN_MONTHS <= months <= _MAX_MONTHS)
            ):
                raise ValidationError(
                    f"months must be an integer between {_MIN_MONTHS} and {_MAX_MONTHS}, "
                    f"got {months!r}."
                )
        return compute_fn(self.db, user_id, **params)
