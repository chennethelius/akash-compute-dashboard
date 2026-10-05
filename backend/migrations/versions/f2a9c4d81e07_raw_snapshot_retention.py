"""Record which source records an inventory snapshot kept."""

from alembic import op
import sqlalchemy as sa

revision = "f2a9c4d81e07"
down_revision = "a314e927bd10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "raw_snapshots",
        sa.Column(
            "retention_policy", sa.String(), nullable=False, server_default="all"
        ),
    )
    op.add_column(
        "raw_snapshots", sa.Column("source_record_count", sa.Integer(), nullable=True)
    )
    op.add_column(
        "raw_snapshots",
        sa.Column("retained_record_count", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column("raw_snapshots", "retained_record_count")
    op.drop_column("raw_snapshots", "source_record_count")
    op.drop_column("raw_snapshots", "retention_policy")
