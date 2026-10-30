"""clear full text of finished articles

Revision ID: a1f3c9d27b10
Revises: c05a5421cbe3
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1f3c9d27b10"
down_revision: str | Sequence[str] | None = "c05a5421cbe3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """The full text is only needed while summarizing; see services/queue.py."""
    op.execute(
        "UPDATE article SET content = NULL WHERE summary_status IN ('DONE', 'FAILED', 'SKIPPED')"
    )


def downgrade() -> None:
    """Deleted text cannot be restored."""
