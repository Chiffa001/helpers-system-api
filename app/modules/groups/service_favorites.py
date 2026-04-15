from uuid import UUID

from sqlalchemy import select

from app.models.group_favorite import GroupFavorite
from app.models.user import User
from app.modules.groups.schemas import GroupFavoriteResponse
from app.modules.groups.service_base import GroupsServiceBase


class GroupsFavoritesMixin(GroupsServiceBase):
    async def favorite_group(
        self,
        group_id: UUID,
        current_user: User,
    ) -> GroupFavoriteResponse:
        await self._require_group_read_access_by_group_id(group_id, current_user)
        favorite = await self.session.scalar(
            select(GroupFavorite).where(
                GroupFavorite.group_id == group_id,
                GroupFavorite.user_id == current_user.id,
            )
        )
        if favorite is None:
            self.session.add(
                GroupFavorite(
                    group_id=group_id,
                    user_id=current_user.id,
                )
            )
            await self.session.commit()
        return GroupFavoriteResponse(is_favorite=True)

    async def unfavorite_group(
        self,
        group_id: UUID,
        current_user: User,
    ) -> GroupFavoriteResponse:
        await self._require_group_read_access_by_group_id(group_id, current_user)
        favorite = await self.session.scalar(
            select(GroupFavorite).where(
                GroupFavorite.group_id == group_id,
                GroupFavorite.user_id == current_user.id,
            )
        )
        if favorite is not None:
            await self.session.delete(favorite)
            await self.session.commit()
        return GroupFavoriteResponse(is_favorite=False)
