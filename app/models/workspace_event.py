from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import WorkspaceEventAudience, WorkspaceEventStatus


class WorkspaceEvent(Base):
    __tablename__ = "workspace_events"

    audience_enum = Enum(
        WorkspaceEventAudience,
        native_enum=False,
        values_callable=lambda enum_cls: [item.value for item in enum_cls],
    )
    status_enum = Enum(
        WorkspaceEventStatus,
        native_enum=False,
        values_callable=lambda enum_cls: [item.value for item in enum_cls],
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    audience: Mapped[WorkspaceEventAudience] = mapped_column(
        audience_enum,
        nullable=False,
        index=True,
    )
    status: Mapped[WorkspaceEventStatus] = mapped_column(
        status_enum,
        default=WorkspaceEventStatus.UPCOMING,
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
