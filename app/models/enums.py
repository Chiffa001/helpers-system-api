from enum import Enum


class WorkspaceStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class WorkspacePlan(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    BUSINESS = "business"


class WorkspaceRole(str, Enum):
    WORKSPACE_ADMIN = "workspace_admin"
    ASSISTANT = "assistant"
    CLIENT = "client"
