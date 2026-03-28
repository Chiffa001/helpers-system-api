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
