from app.modules.workspace_events.service_base import WorkspaceEventsServiceBase
from app.modules.workspace_events.service_writes import WorkspaceEventsWritesMixin


class WorkspaceEventsService(
    WorkspaceEventsWritesMixin,
    WorkspaceEventsServiceBase,
):
    pass
