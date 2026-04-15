from enum import StrEnum


class WorkspaceStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class WorkspacePlan(StrEnum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    BUSINESS = "business"


class WorkspaceRole(StrEnum):
    WORKSPACE_ADMIN = "workspace_admin"
    ASSISTANT = "assistant"
    CLIENT = "client"


class GroupStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class GroupMemberRole(StrEnum):
    ASSISTANT = "assistant"
    CLIENT = "client"


class GroupStageStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class GroupEventStatus(StrEnum):
    UPCOMING = "upcoming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InvoiceStatus(StrEnum):
    ISSUED = "issued"
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class GroupHistoryEventType(StrEnum):
    STAGE_STATUS_CHANGED = "stage_status_changed"
    INVOICE_ISSUED = "invoice_issued"
    INVOICE_PAID = "invoice_paid"
    INVOICE_CANCELLED = "invoice_cancelled"
    INVOICE_EXPIRED = "invoice_expired"
    EVENT_CREATED = "event_created"
    EVENT_CANCELLED = "event_cancelled"
    DOCUMENT_ADDED = "document_added"
    MEMBER_ADDED = "member_added"
    MEMBER_REMOVED = "member_removed"


class BillingPeriod(StrEnum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAST_DUE = "past_due"


class BillingProvider(StrEnum):
    MANUAL = "manual"


class BillingPaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
