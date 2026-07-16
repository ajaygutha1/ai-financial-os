import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.ai.provider.base import ToolDefinition
from app.analytics.engine import AnalyticsEngine
from app.analytics.modules import (
    anomaly_detection,
    burn_rate,
    cash_flow,
    debt_payoff,
    emergency_fund,
    expense_trends,
    ratios,
    retirement_contributions,
    savings_rate,
    subscriptions,
    taxable_events,
)

# `months` is required (not optional) on every tool that takes it -- strict
# tool schemas validate most reliably when every declared property is
# required; the description tells the model the module's own sensible
# default so it isn't guessing.


def _months_schema(default: int) -> dict[str, Any]:
    # Numeric constraints (minimum/maximum) aren't supported in Anthropic
    # tool input schemas -- the valid range is stated in the description
    # instead, and the analytics endpoints themselves still enforce 1-24.
    return {
        "type": "object",
        "properties": {
            "months": {
                "type": "integer",
                "description": (
                    f"Trailing months to analyze, between 1 and 24. Use {default} "
                    "unless the user asks for a different window."
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
    (
        "retirement_contributions",
        "Total retirement-account balance and average net monthly contribution "
        "over a trailing window.",
        _months_schema(retirement_contributions.DEFAULT_MONTHS),
    ),
    (
        "taxable_events",
        "Dividend/interest/buy/sell transaction counts and totals over a trailing window "
        "(not a capital-gains or cost-basis calculation).",
        _months_schema(taxable_events.DEFAULT_MONTHS),
    ),
    (
        "anomaly_detection",
        "Rule-based flags over recent transactions: possible duplicate charges, unusually "
        "large charges for their category, and large first-time charges from a new merchant.",
        _months_schema(anomaly_detection.DEFAULT_MONTHS),
    ),
    (
        "budget_vs_actual",
        "This user's actual spend so far this calendar month vs. the monthly budget target "
        "they've set, per category. Empty if they haven't set any budget targets.",
        _NO_PARAMS_SCHEMA,
    ),
]

_TOOL_SPECS_BY_NAME = {
    name: (name, description, schema) for name, description, schema in _TOOL_SPECS
}


def build_analytics_tools(
    db: Session, user_id: uuid.UUID, *, include: set[str] | None = None
) -> list[ToolDefinition]:
    """One read-only tool per analytics metric, each a thin wrapper around
    AnalyticsEngine.run() -- the registry M3 built with this exact use in
    mind. `include` scopes the tool list to a subset of metric names (by
    default every agent got every metric, which stopped scaling once
    specialist agents arrived in Milestone 6 -- a Tax Advisor calling
    `subscriptions` is just noise)."""
    engine = AnalyticsEngine(db)
    specs = _TOOL_SPECS if include is None else [_TOOL_SPECS_BY_NAME[name] for name in include]

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
        for name, description, schema in specs
    ]
