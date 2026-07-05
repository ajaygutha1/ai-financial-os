import uuid

from fastapi import APIRouter, Depends, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.exceptions import ValidationError
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.csv_import import CsvImportResult
from app.services.csv_import_service import CsvImportService

router = APIRouter(prefix="/imports", tags=["imports"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/csv", response_model=CsvImportResult)
async def import_csv(
    *,
    file: UploadFile,
    account_id: uuid.UUID = Form(...),
    debit_positive: bool = Form(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CsvImportResult:
    if file.content_type not in ("text/csv", "application/vnd.ms-excel", "application/csv"):
        raise ValidationError("Uploaded file must be a CSV.")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValidationError("CSV file exceeds the 10 MB upload limit.")

    service = CsvImportService(db)
    return service.import_csv(
        user_id=current_user.id,
        account_id=account_id,
        content=content,
        debit_positive=debit_positive,
    )
