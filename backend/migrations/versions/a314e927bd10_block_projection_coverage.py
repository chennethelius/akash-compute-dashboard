"""Record marketplace decoding coverage separately from raw archival."""

from alembic import op
import sqlalchemy as sa

revision = "a314e927bd10"
down_revision = "6094166a3f1e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "block_projections",
        sa.Column("chain_id", sa.String(), nullable=False),
        sa.Column("height", sa.BigInteger(), nullable=False),
        sa.Column("decoder_version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("projected_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("chain_id", "height", "decoder_version"),
    )


def downgrade():
    op.drop_table("block_projections")
