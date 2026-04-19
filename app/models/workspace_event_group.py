from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WorkspaceEventGroup(Base):
    __tablename__ = "workspace_event_groups"
    __table_args__ = (
        UniqueConstraint(
            "workspace_event_id",
            "group_id",
            name="uq_workspace_event_groups_event_group",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspace_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
