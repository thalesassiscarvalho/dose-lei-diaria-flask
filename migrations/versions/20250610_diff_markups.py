from alembic import op
import sqlalchemy as sa

revision = "20250610_reset_markup"
down_revision = "bcd73b762318"         # use o head atual que vimos no current --verbose
branch_labels = None
depends_on = None

def upgrade():
    # 1) Remove a tabela antiga (ou renomeia, se quiser backup)
    op.drop_table("user_law_markups")   # plural — a que você quer descartar

    # 2) Cria a nova, do zero
    op.create_table(
        "user_law_markup",              # singular – modelo novo
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("law_id", sa.Integer, nullable=False),
        sa.Column("markup_type", sa.String(20), nullable=False),
        sa.Column("start_offset", sa.Integer, nullable=False),
        sa.Column("end_offset", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime, nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["law_id"],  ["law.id"],  ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "law_id",
                            "start_offset", "end_offset", "markup_type",
                            name="_user_law_markup_uc"),
    )
    op.create_index("idx_markup_lookup", "user_law_markup",
                    ["user_id", "law_id"], unique=False)

def downgrade():
    op.drop_index("idx_markup_lookup", table_name="user_law_markup")
    op.drop_table("user_law_markup")
