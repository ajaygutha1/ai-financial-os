import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics.common import cash_flow_transactions, classify_flow, month_start
from app.repositories.budget_target_repository import BudgetTargetRepository
from app.schemas.analytics import BudgetCategoryActual, BudgetVsActualResponse

METHODOLOGY = (
    "For each category with a user-set monthly budget target: actual spend "
    "this calendar month so far (checking/savings/credit-card expense "
    "activity, transfers and flagged duplicates excluded) vs. the target. "
    "Budgets are inherently monthly, so this always reports the current "
    "calendar month, not a configurable trailing window like other metrics."
)


def compute(db: Session, user_id: uuid.UUID) -> BudgetVsActualResponse:
    as_of = date.today()
    period_start = month_start(as_of)

    targets = BudgetTargetRepository(db).list_for_user(user_id)
    if not targets:
        return BudgetVsActualResponse(categories=[], month=period_start, methodology=METHODOLOGY)

    txns = cash_flow_transactions(db, user_id, date_from=period_start, date_to=as_of)
    actual_by_category_id: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    for t in txns:
        _, expense = classify_flow(t)
        if expense <= 0 or t.category_id is None:
            continue
        actual_by_category_id[t.category_id] += expense

    # Quantized to match every other Numeric(18, 4) money column's
    # precision -- unlike those, this is pure Python Decimal division, which
    # otherwise returns a variable, input-dependent number of decimal places
    # rather than a fixed scale (the same issue Goal.progress_pct has).
    _quantum = Decimal("0.0001")
    categories = []
    for target in targets:
        actual = actual_by_category_id.get(target.category_id, Decimal("0"))
        pct_used = (
            (actual / target.monthly_target_amount * 100).quantize(_quantum)
            if target.monthly_target_amount > 0
            else Decimal("0").quantize(_quantum)
        )
        categories.append(
            BudgetCategoryActual(
                category_id=target.category_id,
                category_name=target.category.name,
                target_amount=target.monthly_target_amount,
                actual_amount=actual,
                remaining=target.monthly_target_amount - actual,
                pct_used=pct_used,
            )
        )

    return BudgetVsActualResponse(
        categories=categories, month=period_start, methodology=METHODOLOGY
    )
