from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WorkspaceEventAudience, WorkspaceEventStatus, WorkspaceRole
from app.models.workspace_event import WorkspaceEvent
from app.models.workspace_event_participant import WorkspaceEventParticipant


def audiences_for_role(role: WorkspaceRole) -> tuple[WorkspaceEventAudience, ...]:
    if role == WorkspaceRole.WORKSPACE_ADMIN:
        return (
            WorkspaceEventAudience.ALL,
            WorkspaceEventAudience.ADMINS,
        )
    if role == WorkspaceRole.ASSISTANT:
        return (
            WorkspaceEventAudience.ALL,
            WorkspaceEventAudience.ASSISTANTS,
        )
    return (WorkspaceEventAudience.ALL,)


async def sync_member_workspace_event_participants(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    role: WorkspaceRole,
) -> None:
    event_ids = (
        await session.scalars(
            select(WorkspaceEvent.id).where(
                WorkspaceEvent.workspace_id == workspace_id,
                WorkspaceEvent.status == WorkspaceEventStatus.UPCOMING,
                WorkspaceEvent.audience.in_(audiences_for_role(role)),
            )
        )
    ).all()
    if not event_ids:
        return

    existing_ids = set(
        (
            await session.scalars(
                select(WorkspaceEventParticipant.workspace_event_id).where(
                    WorkspaceEventParticipant.user_id == user_id,
                    WorkspaceEventParticipant.workspace_event_id.in_(event_ids),
                )
            )
        ).all()
    )
    for event_id in event_ids:
        if event_id in existing_ids:
            continue
        session.add(
            WorkspaceEventParticipant(
                workspace_event_id=event_id,
                user_id=user_id,
            )
        )
