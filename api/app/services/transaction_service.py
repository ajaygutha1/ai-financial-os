import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.transaction import Transaction
from app.models.transaction_provenance import TransactionProvenance
from app.repositories.transaction_provenance_repository import TransactionProvenanceRepository
from app.repositories.transaction_repository import TransactionRepository


class TransactionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.transactions = TransactionRepository(db)
        self.provenance = TransactionProvenanceRepository(db)

    def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        account_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Transaction], int]:
        return self.transactions.list_for_user(
            user_id,
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )

    def get_provenance(
        self, *, user_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> list[TransactionProvenance]:
        transaction = self.transactions.get_by_id(transaction_id)
        if transaction is None or transaction.user_id != user_id:
            raise NotFoundError("Transaction not found.")
        return self.provenance.list_for_transaction(transaction_id)
