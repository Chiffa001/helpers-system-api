from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from app.models.enums import GroupHistoryEventType, GroupStageStatus
from app.models.group_document import GroupDocument
from app.models.group_stage import GroupStage
from app.models.user import User
from app.modules.groups.schemas import (
    GroupDocumentCreateRequest,
    GroupDocumentOut,
    GroupStageCreateRequest,
    GroupStageOut,
    GroupStageUpdateRequest,
)
from app.modules.groups.service_base import GroupsServiceBase


class GroupsDocumentsMixin(GroupsServiceBase):
    async def list_documents(
        self,
        workspace_id: UUID,
        group_id: UUID,
        current_user: User,
    ) -> list[GroupDocumentOut]:
        await self._require_group_read_access(workspace_id, group_id, current_user)
        result = await self.session.scalars(
            select(GroupDocument)
            .where(GroupDocument.group_id == group_id)
            .order_by(GroupDocument.created_at.desc())
        )
        return [GroupDocumentOut.model_validate(item) for item in result.all()]

    async def create_document(
        self,
        workspace_id: UUID,
        group_id: UUID,
        current_user: User,
        payload: GroupDocumentCreateRequest,
    ) -> GroupDocumentOut:
        await self._require_group_write_access(workspace_id, group_id, current_user)
        document = GroupDocument(
            group_id=group_id,
            title=payload.title,
            file_url=payload.file_url,
            body=payload.body,
            created_by_user_id=current_user.id,
        )
        self.session.add(document)
        await self._record_history(
            group_id=group_id,
            actor_user_id=current_user.id,
            event_type=GroupHistoryEventType.DOCUMENT_ADDED,
            payload={
                "document_title": payload.title,
            },
        )
        await self.session.commit()
        await self.session.refresh(document)
        return GroupDocumentOut.model_validate(document)

    async def delete_document(
        self,
        workspace_id: UUID,
        group_id: UUID,
        document_id: UUID,
        current_user: User,
    ) -> None:
        await self._require_group_write_access(workspace_id, group_id, current_user)
        document = await self.session.scalar(
            select(GroupDocument).where(
                GroupDocument.id == document_id,
                GroupDocument.group_id == group_id,
            )
        )
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group document not found",
            )
        await self.session.delete(document)
        await self.session.commit()

    async def list_stages(
        self,
        workspace_id: UUID,
        group_id: UUID,
        current_user: User,
        status_filter: GroupStageStatus | None = None,
    ) -> list[GroupStageOut]:
        await self._require_group_read_access(workspace_id, group_id, current_user)
        stmt = select(GroupStage).where(GroupStage.group_id == group_id)
        if status_filter is not None:
            stmt = stmt.where(GroupStage.status == status_filter)
        stmt = stmt.order_by(GroupStage.created_at.desc())
        result = await self.session.scalars(stmt)
        return [GroupStageOut.model_validate(item) for item in result.all()]

    async def create_stage(
        self,
        workspace_id: UUID,
        group_id: UUID,
        current_user: User,
        payload: GroupStageCreateRequest,
    ) -> GroupStageOut:
        await self._require_group_write_access(workspace_id, group_id, current_user)
        if payload.assigned_to_user_id is not None:
            await self._ensure_group_assistant(group_id, payload.assigned_to_user_id)

        stage = GroupStage(
            group_id=group_id,
            title=payload.title,
            description=payload.description,
            assigned_to_user_id=payload.assigned_to_user_id,
            due_date=payload.due_date,
            created_by_user_id=current_user.id,
        )
        self.session.add(stage)
        await self.session.commit()
        await self.session.refresh(stage)
        return GroupStageOut.model_validate(stage)

    async def update_stage(
        self,
        workspace_id: UUID,
        group_id: UUID,
        stage_id: UUID,
        current_user: User,
        payload: GroupStageUpdateRequest,
    ) -> GroupStageOut:
        await self._require_group_write_access(workspace_id, group_id, current_user)
        stage = await self.session.scalar(
            select(GroupStage).where(
                GroupStage.id == stage_id,
                GroupStage.group_id == group_id,
            )
        )
        if stage is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group stage not found",
            )

        previous_status = stage.status
        if payload.title is not None:
            stage.title = payload.title
        if "description" in payload.model_fields_set:
            stage.description = payload.description
        if (
            "assigned_to_user_id" in payload.model_fields_set
            and payload.assigned_to_user_id is not None
        ):
            await self._ensure_group_assistant(group_id, payload.assigned_to_user_id)
        if "assigned_to_user_id" in payload.model_fields_set:
            stage.assigned_to_user_id = payload.assigned_to_user_id
        if "due_date" in payload.model_fields_set:
            stage.due_date = payload.due_date
        if payload.status is not None:
            stage.status = payload.status

        if previous_status != stage.status:
            await self._record_history(
                group_id=group_id,
                actor_user_id=current_user.id,
                event_type=GroupHistoryEventType.STAGE_STATUS_CHANGED,
                payload={
                    "stage_id": str(stage.id),
                    "title": stage.title,
                    "from_status": previous_status.value,
                    "to_status": stage.status.value,
                },
            )

        await self.session.commit()
        await self.session.refresh(stage)
        return GroupStageOut.model_validate(stage)

    async def delete_stage(
        self,
        workspace_id: UUID,
        group_id: UUID,
        stage_id: UUID,
        current_user: User,
    ) -> None:
        await self._require_group_write_access(workspace_id, group_id, current_user)
        stage = await self.session.scalar(
            select(GroupStage).where(
                GroupStage.id == stage_id,
                GroupStage.group_id == group_id,
            )
        )
        if stage is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group stage not found",
            )
        await self.session.delete(stage)
        await self.session.commit()
