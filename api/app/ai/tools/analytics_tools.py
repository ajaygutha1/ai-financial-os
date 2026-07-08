import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.ai.provider.base import ToolDefinition
from app.analytics.engine import AnalyticsEngine
from app.analytics.modules import (
    burn_rate,
    cash_flow,
    debt_payoff,
    emergency_fund,
    expense_trends,
    ratios,
    savings_rate,
    subscriptions,
)

# `months` is required (not optional) on every tool that takes it -- strict
# tool schemas validate most reliably when every declared property is
# required; the description tells the model the module's own sensible
# default so it isn't guessing.


def _months_schema(default: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "months": {
                "type": "integer",
                "minimum": 1,
                "maximum": 24,
                "description": (
                    f"Trailing months to analyze. Use {default} unless the user "
                    "asks for a different window."
                ),
            }
        },
        "required": ["months"],
        "additionalProperties": False,
    }


_NO_PARAMS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "required": [],
    "additionalProperties": False,
}

_TOOL_SPECS: list[tuple[str, str, dict[str, Any]]] = [
    (
        "net_worth",
        "Current net worth: assets minus liabilities, broken down by account type.",
        _NO_PARAMS_SCHEMA,
    ),
    (
        "cash_flow",
        "Monthly income vs. expenses over a trailing window, plus totals.",
        _months_schema(cash_flow.DEFAULT_MONTHS),
    ),
    (
        "burn_rate",
        "Average monthly net cash burn (or saving) over a trailing window.",
        _months_schema(burn_rate.DEFAULT_MONTHS),
    ),
    (
        "savings_rate",
        "Savings rate ((income - expenses) / income) per month and averaged.",
        _months_schema(savings_rate.DEFAULT_MONTHS),
    ),
    (
        "expense_trends",
        "Category-level spend trends (rising/falling/steady) vs. the trailing average.",
        _months_schema(expense_trends.DEFAULT_MONTHS),
    ),
    (
        "subscriptions",
        "Rule-based detection of recurring subscription-like charges.",
        _months_schema(subscriptions.DEFAULT_MONTHS),
    ),
    (
        "emergency_fund",
        "Liquid assets vs. average monthly expenses, with a health tier label.",
        _months_schema(emergency_fund.DEFAULT_MONTHS),
    ),
    (
        "debt_payoff",
        "Naive payoff projection per credit-card/loan/mortgage account from recent paydown rate.",
        _months_schema(debt_payoff.DEFAULT_MONTHS),
    ),
    (
        "ratios",
        "Composite financial ratios: savings rate, expense/income, liquidity, debt-to-income.",
        _months_schema(ratios.DEFAULT_MONTHS),
    ),
]


def build_analytics_tools(db: Session, user_id: uuid.UUID) -> list[ToolDefinition]:
    """One read-only tool per Milestone 3 analytics metric, each a thin
    wrapper around AnalyticsEngine.run() -- the registry M3 built with this
    exact use in mind."""
    engine = AnalyticsEngine(db)

    def make_handler(metric_name: str) -> Any:
        def handler(tool_input: dict[str, Any]) -> dict[str, Any]:
            result = engine.run(metric_name, user_id, **tool_input)
            return result.model_dump(mode="json")

        return handler

    return [
        ToolDefinition(
            name=name,
            description=description,
            input_schema=schema,
            handler=make_handler(name),
        )
        for name, description, schema in _TOOL_SPECS
    ]
