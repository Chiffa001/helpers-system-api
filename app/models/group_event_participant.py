from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import GroupEventParticipantStatus


class GroupEventParticipant(Base):
    __tablename__ = "group_event_participants"
    __table_args__ = (
        UniqueConstraint(
            "group_event_id",
            "user_id",
            name="uq_group_event_participants_event_user",
        ),
    )

    status_enum = Enum(
        GroupEventParticipantStatus,
        native_enum=False,
        values_callable=lambda enum_cls: [item.value for item in enum_cls],
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    group_event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("group_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[GroupEventParticipantStatus] = mapped_column(
        status_enum,
        default=GroupEventParticipantStatus.INVITED,
        nullable=False,
        index=True,
    )
    is_paid_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    invoice_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
