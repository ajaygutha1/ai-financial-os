from pydantic import BaseModel


class CsvImportResult(BaseModel):
    imported_count: int
    duplicate_count: int
    error_count: int
    errors: list[str]
