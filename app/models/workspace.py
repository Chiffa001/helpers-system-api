from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import WorkspacePlan, WorkspaceStatus


class Workspace(Base):
    __tablename__ = "workspaces"

    status_enum = Enum(
        WorkspaceStatus,
        native_enum=False,
        values_callable=lambda enum_cls: [item.value for item in enum_cls],
    )
    plan_enum = Enum(
        WorkspacePlan,
        native_enum=False,
        values_callable=lambda enum_cls: [item.value for item in enum_cls],
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    bot_token: Mapped[str | None] = mapped_column(String, nullable=True)
    bot_username: Mapped[str | None] = mapped_column(String, nullable=True)
    mini_app_url: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[WorkspaceStatus] = mapped_column(
        status_enum,
        default=WorkspaceStatus.ACTIVE,
        index=True,
        nullable=False,
    )
    plan: Mapped[WorkspacePlan] = mapped_column(
        plan_enum,
        default=WorkspacePlan.FREE,
        nullable=False,
    )
    fee_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        default=Decimal("0.03"),
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    members = relationship("WorkspaceMember", back_populates="workspace")

    @property
    def has_bot(self) -> bool:
        return self.bot_token is not None
