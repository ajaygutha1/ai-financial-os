from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from alembic import command

API_DIR = Path(__file__).parent.parent


def test_migration_0002_is_reversible(engine: Engine) -> None:
    """Drives upgrade -> downgrade(0001) -> upgrade(head) against the same
    database the rest of the suite uses (already at head via the session-
    scoped `engine` fixture), proving 0002's downgrade() actually reverses
    everything it creates -- new tables, the additive columns, and the
    audit_log trigger/function/hash-chain columns.
    """
    alembic_cfg = Config(str(API_DIR / "alembic.ini"))

    command.downgrade(alembic_cfg, "0001")

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    for table_name in (
        "category",
        "merchant",
        "connector_credential",
        "sync_job",
        "domain_events",
        "transaction_provenance",
    ):
        assert table_name not in tables

    transaction_columns = {c["name"] for c in inspector.get_columns("transactions")}
    assert "category_id" not in transaction_columns
    assert "merchant_id" not in transaction_columns

    account_columns = {c["name"] for c in inspector.get_columns("accounts")}
    assert "last_sync_cursor" not in account_columns

    audit_log_columns = {c["name"] for c in inspector.get_columns("audit_log")}
    assert "prev_hash" not in audit_log_columns
    assert "row_hash" not in audit_log_columns

    command.upgrade(alembic_cfg, "head")

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    for table_name in (
        "category",
        "merchant",
        "connector_credential",
        "sync_job",
        "domain_events",
        "transaction_provenance",
    ):
        assert table_name in tables

    transaction_columns = {c["name"] for c in inspector.get_columns("transactions")}
    assert "category_id" in transaction_columns
    assert "merchant_id" in transaction_columns

    audit_log_columns = {c["name"] for c in inspector.get_columns("audit_log")}
    assert "prev_hash" in audit_log_columns
    assert "row_hash" in audit_log_columns
