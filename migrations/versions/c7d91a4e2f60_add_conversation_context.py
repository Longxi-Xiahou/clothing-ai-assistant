"""Add public conversation IDs and persistent search filters."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d91a4e2f60"
down_revision: Union[str, Sequence[str], None] = "b2f73a131927"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add nullable first so existing conversations can be backfilled.
    op.add_column(
        "conversations",
        sa.Column("public_id", sa.String(length=36), nullable=True),
    )

    op.add_column(
        "conversations",
        sa.Column("filters", sa.JSON(), nullable=True),
    )

    # Generate an ID for every existing conversation.
    op.execute(
        sa.text(
            "UPDATE conversations "
            "SET public_id = UUID() "
            "WHERE public_id IS NULL"
        )
    )

    # Existing conversations start with no active filters.
    op.execute(
        sa.text(
            "UPDATE conversations "
            "SET filters = JSON_OBJECT() "
            "WHERE filters IS NULL"
        )
    )

    op.alter_column(
        "conversations",
        "public_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )

    op.alter_column(
        "conversations",
        "filters",
        existing_type=sa.JSON(),
        nullable=False,
    )

    op.create_index(
        "ix_conversations_public_id",
        "conversations",
        ["public_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversations_public_id",
        table_name="conversations",
    )
    op.drop_column("conversations", "filters")
    op.drop_column("conversations", "public_id")
