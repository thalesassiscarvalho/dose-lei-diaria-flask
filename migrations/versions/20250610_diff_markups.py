"""Limpa colunas antigas e garante (markup_type, start_offset, end_offset) para diff."""
from alembic import op
import sqlalchemy as sa

revision = "20250610_diff_markups"
down_revision = None   # substitua pelo número da sua última revision real
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("user_law_markups", recreate="always") as batch_op:
        if batch_op.has_column("content"):
            batch_op.drop_column("content")
        if not batch_op.has_column("markup_type"):
            batch_op.add_column(sa.Column("markup_type", sa.String(length=20), nullable=False))
        if not batch_op.has_column("start_offset"):
            batch_op.add_column(sa.Column("start_offset", sa.Integer(), nullable=False))
        if not batch_op.has_column("end_offset"):
            batch_op.add_column(sa.Column("end_offset", sa.Integer(), nullable=False))
        if batch_op.has_column("selected_text"):
            batch_op.drop_column("selected_text")
        batch_op.create_index("idx_markup_lookup", ["user_id", "law_id"], unique=False)

def downgrade():
    with op.batch_alter_table("user_law_markups", recreate="always") as batch_op:
        batch_op.drop_index("idx_markup_lookup")
        batch_op.add_column(sa.Column("selected_text", sa.Text(), nullable=True))
        batch_op.drop_column("end_offset")
        batch_op.drop_column("start_offset")
        batch_op.drop_column("markup_type")
        batch_op.add_column(sa.Column("content", sa.Text(), nullable=True))
