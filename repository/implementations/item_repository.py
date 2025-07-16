from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from database.sqlalchemy_connect import sess_db
from models.request.item import ItemCreate
from models.response.RepositoryResponse import RepositoryResponse
from utils.handle_repo_errors import handle_repo_errors
from utils.make_repo_response import make_repo_response
from models.data.item import Item
from repository.interfaces.item_repository import IItemRepository

class ItemRepositoryImpl(IItemRepository):
    """Implementation of the item repository interfaces"""

    def __init__(self, session: AsyncSession = Depends(sess_db)):
        self.sess: AsyncSession = session

    @handle_repo_errors
    async def create_item(self, item: ItemCreate) -> RepositoryResponse:
        """Create a new freelancer item"""
        item_entity = Item(**item.model_dump())
        self.sess.add(item_entity)
        await self.sess.commit()
        await self.sess.refresh(item_entity)

        return make_repo_response("success", "ITEM_CREATED", "Freelancer item created successfully", item_entity)

    @handle_repo_errors
    async def get_item(self, id: str) -> RepositoryResponse:
        """Get a freelancer item by item_id"""
        try:
            # Convert string id to integer
            item_id = int(id)
            query = await self.sess.execute(select(Item).filter(Item.item_id == item_id))
            result = query.scalars().first()

            if not result:
                return make_repo_response("error", "ITEM_NOT_FOUND", f"Freelancer item for user {id} not found")

            return make_repo_response("success", "ITEM_FOUND", f"Freelancer item for user {id} found", result)
        except ValueError:
            # Handle case where id cannot be converted to integer
            return make_repo_response("error", "INVALID_ID", f"Invalid item_id format: {id} is not a valid integer")

    @handle_repo_errors
    async def update_item(self, item: ItemCreate, id: str) -> RepositoryResponse:
        """Update an existing freelancer item"""
        try:
            # Convert string id to integer
            item_id = int(id)
            query = await self.sess.execute(select(Item).filter(Item.item_id == item_id))
            result = query.scalars().first()

            if not result:
                return make_repo_response("error", "ITEM_NOT_FOUND", f"Freelancer item for user {id} not found")

            for key, value in item.model_dump().items():
                setattr(result, key, value)

            await self.sess.commit()
            await self.sess.refresh(result)

            return make_repo_response("success", "ITEM_UPDATED", "Freelancer item updated successfully", result)
        except ValueError:
            # Handle case where id cannot be converted to integer
            return make_repo_response("error", "INVALID_ID", f"Invalid item_id format: {id} is not a valid integer")

    @handle_repo_errors
    async def delete_item(self, id: str) -> RepositoryResponse:
        """Delete an existing freelancer item"""
        try:
            # Convert string id to integer
            item_id = int(id)
            query = await self.sess.execute(select(Item).filter(Item.item_id == item_id))
            result = query.scalars().first()
            if not result:
                return make_repo_response("error", "ITEM_NOT_FOUND", f"Freelancer item for user {id} not found")
            await self.sess.delete(result)
            await self.sess.commit()
            return make_repo_response("success", "ITEM_DELETED", "Freelancer item deleted successfully", id)
        except ValueError:
            # Handle case where id cannot be converted to integer
            return make_repo_response("error", "INVALID_ID", f"Invalid item_id format: {id} is not a valid integer")
