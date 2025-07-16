from abc import ABC, abstractmethod
from models.request.item import ItemCreate
from models.response.RepositoryResponse import RepositoryResponse

class IItemRepository(ABC):
    """Interface for item repository operations"""
    @abstractmethod
    async def create_item(self, item: ItemCreate) -> RepositoryResponse:
        """Create a new freelancer item"""
        pass

    @abstractmethod
    async def get_item(self, id: str) -> RepositoryResponse:
        """Get a freelancer item by item_id"""
        pass

    @abstractmethod
    async def update_item(self, item: ItemCreate, id: str) -> RepositoryResponse:
        """Update an existing freelancer item"""
        pass

    @abstractmethod
    async def delete_item(self, id: str) -> RepositoryResponse:
        """Delete an existing freelancer item"""
        pass