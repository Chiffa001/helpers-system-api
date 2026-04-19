from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    GroupEventStatus,
    GroupHistoryEventType,
    GroupMemberRole,
    GroupStageStatus,
    GroupStatus,
    InvoiceStatus,
    WorkspaceEventStatus,
)


class GroupCreateRequest(BaseModel):
    title: str
    description: str | None = None


class GroupUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: GroupStatus | None = None


class GroupOut(BaseModel):
    id: UUID
    workspace_id: UUID
    title: str
    description: str | None
    status: GroupStatus
    is_favorite: bool = False
    created_by_user_id: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GroupFavoriteResponse(BaseModel):
    is_favorite: bool


class GroupMemberUser(BaseModel):
    id: UUID
    full_name: str
    username: str | None


class GroupMemberResponse(BaseModel):
    id: UUID
    user: GroupMemberUser
    role: GroupMemberRole
    is_active: bool
    joined_at: datetime


class GroupMemberCreateRequest(BaseModel):
    user_id: UUID
    role: GroupMemberRole


class GroupDocumentCreateRequest(BaseModel):
    title: str
    file_url: str | None = None
    body: str | None = None

    @model_validator(mode="after")
    def validate_content(self) -> GroupDocumentCreateRequest:
        if not self.file_url and not self.body:
            raise ValueError("Either file_url or body must be provided")
        return self


class GroupDocumentOut(BaseModel):
    id: UUID
    group_id: UUID
    title: str
    file_url: str | None
    body: str | None
    created_by_user_id: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GroupStageCreateRequest(BaseModel):
    title: str
    description: str | None = None
    assigned_to_user_id: UUID | None = None
    due_date: datetime | None = None


class GroupStageUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: GroupStageStatus | None = None
    assigned_to_user_id: UUID | None = None
    due_date: datetime | None = None


class GroupStageOut(BaseModel):
    id: UUID
    group_id: UUID
    title: str
    description: str | None
    status: GroupStageStatus
    assigned_to_user_id: UUID | None
    due_date: datetime | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GroupEventCreateRequest(BaseModel):
    title: str
    description: str | None = None
    date: datetime
    location: str | None = None
    is_paid: bool = False
    amount: Decimal | None = None
    currency: str | None = None
    due_date: datetime | None = None

    @model_validator(mode="after")
    def validate_paid_amount(self) -> GroupEventCreateRequest:
        if self.is_paid and self.amount is None:
            raise ValueError("amount is required for paid events")
        if self.is_paid and self.currency is None:
            raise ValueError("currency is required for paid events")
        if not self.is_paid and self.amount is not None:
            raise ValueError("amount must be null for free events")
        if not self.is_paid and self.currency is not None:
            raise ValueError("currency must be null for free events")
        if not self.is_paid and self.due_date is not None:
            raise ValueError("due_date must be null for free events")
        return self


class GroupEventUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    date: datetime | None = None
    location: str | None = None
    is_paid: bool | None = None
    amount: Decimal | None = None
    currency: str | None = None
    due_date: datetime | None = None
    status: GroupEventStatus | None = None


class GroupEventOut(BaseModel):
    id: UUID
    group_id: UUID
    title: str
    description: str | None
    date: datetime
    location: str | None
    is_paid: bool
    amount: Decimal | None
    currency: str | None
    due_date: datetime | None
    status: GroupEventStatus
    created_by_user_id: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceShortOut(BaseModel):
    id: UUID
    amount: Decimal
    status: InvoiceStatus
    due_date: datetime | None


class GroupFeedEventOut(BaseModel):
    type: Literal["group"] = "group"
    id: UUID
    title: str
    date: datetime
    location: str | None = None
    status: GroupEventStatus
    is_paid: bool
    amount: Decimal | None
    currency: str | None = None
    my_participant_status: str | None = None
    my_invoice: InvoiceShortOut | None = None


class ParticipantSummaryOut(BaseModel):
    total: int
    accepted: int
    declined: int
    pending: int


class WorkspaceFeedEventOut(BaseModel):
    type: Literal["workspace"] = "workspace"
    id: UUID
    title: str
    date: datetime
    location: str | None = None
    status: WorkspaceEventStatus
    audience: str
    my_response: str | None = None
    participants_summary: ParticipantSummaryOut | None = None


FeedEventOut = Annotated[GroupFeedEventOut | WorkspaceFeedEventOut, Field(discriminator="type")]


class EventsFeedResponse(BaseModel):
    items: list[FeedEventOut]
    total: int


class InvoiceCreateRequest(BaseModel):
    group_event_id: UUID | None = None
    client_user_id: UUID
    amount: Decimal
    due_date: datetime | None = None


class InvoiceUpdateRequest(BaseModel):
    status: InvoiceStatus | None = None
    due_date: datetime | None = None


class InvoicePayRequest(BaseModel):
    tx_hash: str


class InvoiceOut(BaseModel):
    id: UUID
    group_event_id: UUID | None
    group_id: UUID
    client_user_id: UUID
    amount: Decimal
    status: InvoiceStatus
    due_date: datetime | None
    tx_hash: str | None
    paid_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GroupHistoryEntryOut(BaseModel):
    id: UUID
    group_id: UUID
    actor_user_id: UUID | None
    event_type: GroupHistoryEventType
    payload: dict[str, object]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
