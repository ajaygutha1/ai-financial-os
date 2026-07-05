import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.core.exceptions import ValidationError

# Column-header aliases we recognize across common bank/credit-card CSV exports.
DATE_ALIASES = {"date", "posted date", "transaction date", "posting date", "trans date"}
AMOUNT_ALIASES = {"amount", "transaction amount", "debit/credit", "value"}
DEBIT_ALIASES = {"debit"}
CREDIT_ALIASES = {"credit"}
DESCRIPTION_ALIASES = {"description", "memo", "payee", "name", "transaction description"}

DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%B %d, %Y")


@dataclass
class ParsedRow:
    row_number: int
    posted_at: date
    amount: Decimal
    description: str
    raw_row: dict[str, str]


@dataclass
class ParseError:
    row_number: int
    message: str
    raw_row: dict[str, str]


@dataclass
class ParseResult:
    rows: list[ParsedRow]
    errors: list[ParseError]


def _normalize_header(header: str) -> str:
    return header.strip().lower()


def _find_column(headers: list[str], aliases: set[str]) -> str | None:
    for header in headers:
        if _normalize_header(header) in aliases:
            return header
    return None


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(raw: str) -> Decimal | None:
    cleaned = raw.strip().replace("$", "").replace(",", "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_csv(content: bytes, *, debit_positive: bool) -> ParseResult:
    """Parse raw CSV bytes into normalized rows.

    `debit_positive` reflects how the source bank encodes outflows: if True, the
    file represents money leaving the account as a positive number and we flip
    the sign so our internal convention (negative = outflow) holds consistently
    across every ingestion source.
    """
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("CSV file is not valid UTF-8 text.") from exc

    try:
        dialect = csv.Sniffer().sniff(text.splitlines()[0] if text else "")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValidationError("CSV file has no header row.")

    headers = list(reader.fieldnames)
    date_col = _find_column(headers, DATE_ALIASES)
    amount_col = _find_column(headers, AMOUNT_ALIASES)
    debit_col = _find_column(headers, DEBIT_ALIASES)
    credit_col = _find_column(headers, CREDIT_ALIASES)
    description_col = _find_column(headers, DESCRIPTION_ALIASES)

    if date_col is None:
        raise ValidationError("Could not find a date column in the CSV header.")
    if amount_col is None and (debit_col is None or credit_col is None):
        raise ValidationError(
            "Could not find an amount column (or separate debit/credit columns) in the CSV header."
        )
    if description_col is None:
        raise ValidationError("Could not find a description column in the CSV header.")

    rows: list[ParsedRow] = []
    errors: list[ParseError] = []

    for row_number, raw_row in enumerate(reader, start=2):  # header is row 1
        posted_at = _parse_date(raw_row.get(date_col, ""))
        if posted_at is None:
            errors.append(ParseError(row_number, "Unparseable date.", raw_row))
            continue

        if amount_col is not None:
            amount = _parse_decimal(raw_row.get(amount_col, ""))
            if amount is not None and debit_positive:
                amount = -amount
        else:
            debit = _parse_decimal(raw_row.get(debit_col, "")) if debit_col else None
            credit = _parse_decimal(raw_row.get(credit_col, "")) if credit_col else None
            if debit:
                amount = -abs(debit)
            elif credit:
                amount = abs(credit)
            else:
                amount = None

        if amount is None:
            errors.append(ParseError(row_number, "Unparseable amount.", raw_row))
            continue

        description = raw_row.get(description_col, "").strip()
        rows.append(
            ParsedRow(
                row_number=row_number,
                posted_at=posted_at,
                amount=amount,
                description=description,
                raw_row=raw_row,
            )
        )

    return ParseResult(rows=rows, errors=errors)
