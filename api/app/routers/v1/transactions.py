import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.transaction_provenance import TransactionProvenance
from app.models.user import User
from app.schemas.transaction import (
    TransactionListResponse,
    TransactionProvenancePublic,
    TransactionPublic,
)
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    account_id: uuid.UUID | None = None,
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    service = TransactionService(db)
    items, total = service.list_for_user(
        current_user.id,
        account_id=account_id,
        date_from=from_,
        date_to=to,
        page=page,
        page_size=page_size,
    )
    return TransactionListResponse(
        items=[TransactionPublic.model_validate(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{transaction_id}/provenance", response_model=list[TransactionProvenancePublic])
def get_transaction_provenance(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TransactionProvenance]:
    service = TransactionService(db)
    return service.get_provenance(user_id=current_user.id, transaction_id=transaction_id)
