"""fix_workspaces_created_by_fk_on_delete"""

from collections.abc import Sequence

from alembic import op

revision: str = "db5c339b4f78"
down_revision: str | None = "0001_step0_init"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "workspaces_created_by_user_id_fkey",
        "workspaces",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "workspaces_created_by_user_id_fkey",
        "workspaces",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "workspaces_created_by_user_id_fkey",
        "workspaces",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "workspaces_created_by_user_id_fkey",
        "workspaces",
        "users",
        ["created_by_user_id"],
        ["id"],
    )
