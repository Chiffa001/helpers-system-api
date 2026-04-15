from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from app.models.enums import (
    GroupHistoryEventType,
    GroupMemberRole,
    InvoiceStatus,
    WorkspaceRole,
)
from app.models.invoice import Invoice
from app.models.user import User
from app.modules.groups.schemas import (
    InvoiceCreateRequest,
    InvoiceOut,
    InvoicePayRequest,
    InvoiceUpdateRequest,
)
from app.modules.groups.service_base import GroupsServiceBase


class GroupsInvoicesMixin(GroupsServiceBase):
    async def list_invoices(
        self,
        workspace_id: UUID,
        group_id: UUID,
        current_user: User,
        status_filter: InvoiceStatus | None = None,
    ) -> list[InvoiceOut]:
        ctx = await self._require_group_read_access(workspace_id, group_id, current_user)
        stmt = select(Invoice).where(Invoice.group_id == group_id)
        if status_filter is not None:
            stmt = stmt.where(Invoice.status == status_filter)
        if ctx.group_member_role == GroupMemberRole.CLIENT:
            stmt = stmt.where(Invoice.client_user_id == current_user.id)
        stmt = stmt.order_by(Invoice.created_at.desc())
        result = await self.session.scalars(stmt)
        return [InvoiceOut.model_validate(item) for item in result.all()]

    async def create_invoice(
        self,
        workspace_id: UUID,
        group_id: UUID,
        current_user: User,
        payload: InvoiceCreateRequest,
    ) -> InvoiceOut:
        await self._require_group_write_access(workspace_id, group_id, current_user)
        await self._ensure_group_client(group_id, payload.client_user_id)
        if payload.group_event_id is not None:
            await self._ensure_group_event(group_id, payload.group_event_id)

        invoice = Invoice(
            group_id=group_id,
            group_event_id=payload.group_event_id,
            client_user_id=payload.client_user_id,
            amount=payload.amount,
            due_date=payload.due_date,
        )
        self.session.add(invoice)
        await self.session.flush()
        await self._record_history(
            group_id=group_id,
            actor_user_id=current_user.id,
            event_type=GroupHistoryEventType.INVOICE_ISSUED,
            payload={
                "invoice_id": str(invoice.id),
                "client_user_id": str(invoice.client_user_id),
                "amount": self._decimal(invoice.amount),
                "status": invoice.status.value,
            },
        )
        await self.session.commit()
        await self.session.refresh(invoice)
        return InvoiceOut.model_validate(invoice)

    async def update_invoice(
        self,
        workspace_id: UUID,
        group_id: UUID,
        invoice_id: UUID,
        current_user: User,
        payload: InvoiceUpdateRequest,
    ) -> InvoiceOut:
        ctx = await self._require_group_write_access(workspace_id, group_id, current_user)
        invoice = await self.session.scalar(
            select(Invoice).where(
                Invoice.id == invoice_id,
                Invoice.group_id == group_id,
            )
        )
        if invoice is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )

        previous_status = invoice.status
        next_status = payload.status if payload.status is not None else invoice.status
        if "due_date" in payload.model_fields_set:
            invoice.due_date = payload.due_date
        if next_status == InvoiceStatus.PAID and ctx.actor_role == WorkspaceRole.ASSISTANT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Assistant cannot manually confirm invoice payment",
            )
        if payload.status is not None:
            invoice.status = payload.status

        if next_status == InvoiceStatus.PAID:
            invoice.paid_at = datetime.now(UTC)
        elif previous_status == InvoiceStatus.PAID and next_status in {
            InvoiceStatus.ISSUED,
            InvoiceStatus.PENDING_PAYMENT,
            InvoiceStatus.CANCELLED,
            InvoiceStatus.EXPIRED,
        }:
            invoice.paid_at = None

        if (
            previous_status != invoice.status
            and (history_event := self._invoice_history_event(invoice.status)) is not None
        ):
            await self._record_history(
                group_id=group_id,
                actor_user_id=current_user.id,
                event_type=history_event,
                payload={
                    "invoice_id": str(invoice.id),
                    "client_user_id": str(invoice.client_user_id),
                    "amount": self._decimal(invoice.amount),
                    "status": invoice.status.value,
                },
            )

        await self.session.commit()
        await self.session.refresh(invoice)
        return InvoiceOut.model_validate(invoice)

    async def pay_invoice(
        self,
        workspace_id: UUID,
        group_id: UUID,
        invoice_id: UUID,
        current_user: User,
        payload: InvoicePayRequest,
    ) -> InvoiceOut:
        ctx = await self._require_group_read_access(workspace_id, group_id, current_user)
        invoice = await self.session.scalar(
            select(Invoice).where(
                Invoice.id == invoice_id,
                Invoice.group_id == group_id,
            )
        )
        if invoice is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )

        if (
            not current_user.is_super_admin
            and ctx.actor_role != WorkspaceRole.WORKSPACE_ADMIN
            and (
                ctx.group_member_role != GroupMemberRole.CLIENT
                or invoice.client_user_id != current_user.id
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invoice access denied",
            )

        if invoice.status not in {InvoiceStatus.ISSUED, InvoiceStatus.PENDING_PAYMENT}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Invoice is not payable",
            )

        invoice.status = InvoiceStatus.PENDING_PAYMENT
        invoice.payment_tx_hash = payload.payment_tx_hash
        await self.session.commit()
        await self.session.refresh(invoice)
        return InvoiceOut.model_validate(invoice)
