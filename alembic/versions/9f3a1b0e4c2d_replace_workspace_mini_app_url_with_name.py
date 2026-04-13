"""replace workspace mini_app_url with bot_mini_app_name"""

from collections.abc import Sequence
from urllib.parse import urlparse

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "9f3a1b0e4c2d"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _extract_bot_parts(mini_app_url: str | None) -> tuple[str | None, str | None]:
    if not mini_app_url:
        return None, None

    parsed = urlparse(mini_app_url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None, None

    return parts[0], parts[1]


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("bot_mini_app_name", sa.Text(), nullable=True))

    connection = op.get_bind()
    workspaces = sa.table(
        "workspaces",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("bot_username", sa.Text()),
        sa.column("mini_app_url", sa.Text()),
        sa.column("bot_mini_app_name", sa.Text()),
    )

    rows = connection.execute(
        sa.select(
            workspaces.c.id,
            workspaces.c.bot_username,
            workspaces.c.mini_app_url,
        )
    ).mappings()

    for row in rows:
        parsed_username, parsed_app_name = _extract_bot_parts(row["mini_app_url"])
        update_values: dict[str, str] = {}

        if not row["bot_username"] and parsed_username:
            update_values["bot_username"] = parsed_username
        if parsed_app_name:
            update_values["bot_mini_app_name"] = parsed_app_name

        if update_values:
            connection.execute(
                workspaces.update().where(workspaces.c.id == row["id"]).values(**update_values)
            )

    op.drop_column("workspaces", "mini_app_url")


def downgrade() -> None:
    op.add_column("workspaces", sa.Column("mini_app_url", sa.Text(), nullable=True))

    connection = op.get_bind()
    workspaces = sa.table(
        "workspaces",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("bot_username", sa.Text()),
        sa.column("mini_app_url", sa.Text()),
        sa.column("bot_mini_app_name", sa.Text()),
    )

    rows = connection.execute(
        sa.select(
            workspaces.c.id,
            workspaces.c.bot_username,
            workspaces.c.bot_mini_app_name,
        )
    ).mappings()

    for row in rows:
        if row["bot_username"] and row["bot_mini_app_name"]:
            connection.execute(
                workspaces.update()
                .where(workspaces.c.id == row["id"])
                .values(
                    mini_app_url=(f"https://t.me/{row['bot_username']}/{row['bot_mini_app_name']}")
                )
            )

    op.drop_column("workspaces", "bot_mini_app_name")
