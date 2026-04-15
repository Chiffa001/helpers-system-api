from app.modules.groups.service_base import GroupsServiceBase
from app.modules.groups.service_documents import GroupsDocumentsMixin
from app.modules.groups.service_events import GroupsEventsMixin
from app.modules.groups.service_favorites import GroupsFavoritesMixin
from app.modules.groups.service_groups import GroupsCoreMixin
from app.modules.groups.service_invoices import GroupsInvoicesMixin


class GroupsService(
    GroupsCoreMixin,
    GroupsDocumentsMixin,
    GroupsEventsMixin,
    GroupsInvoicesMixin,
    GroupsFavoritesMixin,
    GroupsServiceBase,
):
    pass
