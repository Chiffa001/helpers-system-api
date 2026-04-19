from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import WorkspaceEventResponse


class WorkspaceEventParticipant(Base):
    __tablename__ = "workspace_event_participants"
    __table_args__ = (
        UniqueConstraint(
            "workspace_event_id",
            "user_id",
            name="uq_workspace_event_participants_event_user",
        ),
    )

    response_enum = Enum(
        WorkspaceEventResponse,
        native_enum=False,
        values_callable=lambda enum_cls: [item.value for item in enum_cls],
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspace_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    response: Mapped[WorkspaceEventResponse] = mapped_column(
        response_enum,
        default=WorkspaceEventResponse.PENDING,
        nullable=False,
        index=True,
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
