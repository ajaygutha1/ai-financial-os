"""ingestion breadth and enhancements

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-05 12:21:07.424205

"""

import hashlib
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Must match app/core/audit_hash.py's GENESIS_HASH -- duplicated here rather
# than imported because migrations are frozen historical records that
# shouldn't depend on application code that can change later.
GENESIS_HASH = "0" * 64


def upgrade() -> None:
    op.create_table(
        "category",
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["category.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_id", "name", name="ux_category_parent_name"),
    )
    op.create_index(
        "ux_category_top_level_name",
        "category",
        ["name"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NULL"),
    )

    op.create_table(
        "domain_events",
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.UUID(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_domain_events_aggregate",
        "domain_events",
        ["aggregate_type", "aggregate_id"],
        unique=False,
    )
    op.create_index("ix_domain_events_event_type", "domain_events", ["event_type"], unique=False)
    op.create_index("ix_domain_events_occurred_at", "domain_events", ["occurred_at"], unique=False)

    op.create_table(
        "connector_credential",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_item_id", sa.String(length=255), nullable=True),
        sa.Column("access_token_enc", sa.String(), nullable=True),
        sa.Column("refresh_token_enc", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="ux_connector_credential_user_provider"),
    )
    op.create_index(
        "ix_connector_credential_user_id", "connector_credential", ["user_id"], unique=False
    )

    op.create_table(
        "merchant",
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["category_id"], ["category.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_merchant_canonical_name_lower",
        "merchant",
        [sa.literal_column("lower(canonical_name)")],
        unique=True,
    )

    op.create_table(
        "sync_job",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cursor_before", sa.String(length=255), nullable=True),
        sa.Column("cursor_after", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("reconciliation_status", sa.String(length=16), nullable=True),
        sa.Column("discrepancy_amount", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_job_account_id", "sync_job", ["account_id"], unique=False)
    op.create_index("ix_sync_job_status", "sync_job", ["status"], unique=False)
    op.create_index(
        "ux_sync_job_idempotency_key_active",
        "sync_job",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("status != 'failed'"),
    )

    op.create_table(
        "transaction_provenance",
        sa.Column("transaction_id", sa.UUID(), nullable=False),
        sa.Column("sync_job_id", sa.UUID(), nullable=True),
        sa.Column("step", sa.String(length=64), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["sync_job_id"], ["sync_job.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transaction_provenance_sync_job_id",
        "transaction_provenance",
        ["sync_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_transaction_provenance_transaction_id",
        "transaction_provenance",
        ["transaction_id"],
        unique=False,
    )

    op.add_column("accounts", sa.Column("last_sync_cursor", sa.String(length=255), nullable=True))

    op.add_column("transactions", sa.Column("category_id", sa.UUID(), nullable=True))
    op.add_column("transactions", sa.Column("merchant_id", sa.UUID(), nullable=True))
    op.create_index("ix_transactions_category_id", "transactions", ["category_id"], unique=False)
    op.create_index("ix_transactions_merchant_id", "transactions", ["merchant_id"], unique=False)
    op.create_foreign_key(
        "fk_transactions_category_id_category",
        "transactions",
        "category",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_transactions_merchant_id_merchant",
        "transactions",
        "merchant",
        ["merchant_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- audit_log hash chain (Enhancement 2) ---
    # Added nullable first because existing rows predate the chain; backfilled
    # procedurally (the chain is inherently sequential, not expressible as a
    # single SQL UPDATE), then made non-null.
    op.add_column("audit_log", sa.Column("prev_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_log", sa.Column("row_hash", sa.String(length=64), nullable=True))
    _backfill_audit_log_hash_chain()
    op.alter_column("audit_log", "prev_hash", nullable=False)
    op.alter_column("audit_log", "row_hash", nullable=False)

    # --- audit_log immutability trigger ---
    # A trigger, not a bare REVOKE: this project has one Postgres role
    # (the migration-owning role is also the app's runtime role), and Postgres
    # table owners are unaffected by REVOKE on their own table -- issuing one
    # here would be no-op security theater. A trigger rejects the mutation
    # regardless of which role attempts it. Revisit with real role separation
    # (a distinct least-privileged app role) in Milestone 8.
    op.execute(
        """
        CREATE FUNCTION reject_audit_log_mutation() RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log rows are immutable';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation();
        """
    )
    # Row-level DELETE triggers do not fire on TRUNCATE (a distinct Postgres
    # trigger event) -- without this, TRUNCATE would silently bypass the
    # immutability guarantee entirely. Same function, statement-level.
    op.execute(
        """
        CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_log
        FOR EACH STATEMENT EXECUTE FUNCTION reject_audit_log_mutation();
        """
    )


def _backfill_audit_log_hash_chain() -> None:
    """Computes prev_hash/row_hash for any pre-existing audit_log rows, in
    creation order. Must stay in sync with app/core/audit_hash.py's algorithm.
    """
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, event_type, user_id, metadata, created_at "
            "FROM audit_log ORDER BY created_at, id"
        )
    ).fetchall()

    prev_hash = GENESIS_HASH
    for row in rows:
        payload = (
            f"{prev_hash}{row.event_type}{row.user_id}"
            f"{json.dumps(row.metadata, sort_keys=True, default=str)}"
            f"{row.created_at.isoformat()}"
        )
        row_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        bind.execute(
            sa.text(
                "UPDATE audit_log SET prev_hash = :prev_hash, row_hash = :row_hash WHERE id = :id"
            ),
            {"prev_hash": prev_hash, "row_hash": row_hash, "id": row.id},
        )
        prev_hash = row_hash


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_truncate ON audit_log")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_log")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_log_mutation()")

    op.drop_column("audit_log", "row_hash")
    op.drop_column("audit_log", "prev_hash")

    op.drop_constraint("fk_transactions_merchant_id_merchant", "transactions", type_="foreignkey")
    op.drop_constraint("fk_transactions_category_id_category", "transactions", type_="foreignkey")
    op.drop_index("ix_transactions_merchant_id", table_name="transactions")
    op.drop_index("ix_transactions_category_id", table_name="transactions")
    op.drop_column("transactions", "merchant_id")
    op.drop_column("transactions", "category_id")

    op.drop_column("accounts", "last_sync_cursor")

    op.drop_index("ix_transaction_provenance_transaction_id", table_name="transaction_provenance")
    op.drop_index("ix_transaction_provenance_sync_job_id", table_name="transaction_provenance")
    op.drop_table("transaction_provenance")

    op.drop_index(
        "ux_sync_job_idempotency_key_active",
        table_name="sync_job",
        postgresql_where=sa.text("status != 'failed'"),
    )
    op.drop_index("ix_sync_job_status", table_name="sync_job")
    op.drop_index("ix_sync_job_account_id", table_name="sync_job")
    op.drop_table("sync_job")

    op.drop_index("ux_merchant_canonical_name_lower", table_name="merchant")
    op.drop_table("merchant")

    op.drop_index("ix_connector_credential_user_id", table_name="connector_credential")
    op.drop_table("connector_credential")

    op.drop_index("ix_domain_events_occurred_at", table_name="domain_events")
    op.drop_index("ix_domain_events_event_type", table_name="domain_events")
    op.drop_index("ix_domain_events_aggregate", table_name="domain_events")
    op.drop_table("domain_events")

    op.drop_index(
        "ux_category_top_level_name",
        table_name="category",
        postgresql_where=sa.text("parent_id IS NULL"),
    )
    op.drop_table("category")
