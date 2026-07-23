import pytest

from app.ingestion.connectors.plaid.real_client import RealPlaidClient, _map_account_type
from app.models.account import AccountType


@pytest.mark.parametrize(
    ("plaid_type", "plaid_subtype", "expected"),
    [
        ("depository", "checking", AccountType.CHECKING.value),
        ("depository", "savings", AccountType.SAVINGS.value),
        ("credit", "credit card", AccountType.CREDIT_CARD.value),
        ("loan", "mortgage", AccountType.MORTGAGE.value),
        ("loan", "student", AccountType.LOAN.value),
        ("investment", "401k", AccountType.RETIREMENT.value),
        ("investment", "brokerage", AccountType.INVESTMENT.value),
        ("brokerage", None, AccountType.INVESTMENT.value),
        ("depository", None, AccountType.CHECKING.value),
        ("credit", None, AccountType.CREDIT_CARD.value),
        ("something_unmapped", "something_unmapped", AccountType.OTHER.value),
    ],
)
def test_map_account_type(plaid_type: str, plaid_subtype: str | None, expected: str) -> None:
    assert _map_account_type(plaid_type, plaid_subtype) == expected


def test_real_plaid_client_rejects_unsupported_environment() -> None:
    with pytest.raises(ValueError, match="Unsupported plaid_env"):
        RealPlaidClient(client_id="id", secret="secret", environment="staging")


def test_real_plaid_client_accepts_sandbox() -> None:
    client = RealPlaidClient(client_id="id", secret="secret", environment="sandbox")
    assert client is not None
