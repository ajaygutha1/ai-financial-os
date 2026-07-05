import uuid

from fastapi import APIRouter, Depends, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.exceptions import ValidationError
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.imports import ImportResult
from app.services.csv_import_service import CsvImportService
from app.services.ofx_import_service import OfxImportService

router = APIRouter(prefix="/imports", tags=["imports"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/csv", response_model=ImportResult)
async def import_csv(
    *,
    file: UploadFile,
    account_id: uuid.UUID = Form(...),
    debit_positive: bool = Form(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportResult:
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


@router.post("/ofx", response_model=ImportResult)
async def import_ofx(
    *,
    file: UploadFile,
    account_id: uuid.UUID = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportResult:
    # OFX/QFX content-type reporting is inconsistent across banks and
    # browsers (application/x-ofx, application/vnd.intu.qfx, octet-stream,
    # even text/plain) -- rely on the parser itself to reject invalid content
    # rather than guessing at MIME types here.
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValidationError("OFX/QFX file exceeds the 10 MB upload limit.")

    service = OfxImportService(db)
    return service.import_ofx(
        user_id=current_user.id,
        account_id=account_id,
        content=content,
    )
