from typing import Any

from utils.logger import logger, log_performance_async
from utils.cache import cache, invalidate_cache

from fastapi import Depends, UploadFile

from exceptions_handler import BadRequestException, NotFoundException, UnexpectedException, NotAuthorizedException
from models.request.item import ItemCreate
from models.response.StandardResponse import StandardResponse
from repository.interfaces.item_repository import IItemRepository
from repository.implementations.item_repository import ItemRepositoryImpl
from constants import (LOG_ITEM_CREATED, LOG_ITEM_RETRIEVED,
    LOG_ITEM_UPDATED, ERROR_CODE_ITEM_NOT_FOUND, ERROR_ITEM_NOT_FOUND, LOG_ITEM_DELETED
)


class ItemService:
    def __init__(self,
                item_repository: IItemRepository = Depends(ItemRepositoryImpl)):
        self.repo: IItemRepository = item_repository

    @log_performance_async(threshold_ms=200)
    async def create_item(self, item: ItemCreate) -> StandardResponse:

        result = await self.repo.create_item(item)

        logger.info(
            LOG_ITEM_CREATED,
            extra={
                "item_id": result.data.item_id if hasattr(result.data, 'item_id') else None
            }
        )


        return StandardResponse(
            status=result.status,
            message=result.message,
            data=result.data.to_dict()
        )

    @log_performance_async(threshold_ms=200)
    @cache(ttl=300, prefix="item")
    async def get_item(self, item_id: str) -> StandardResponse:
        logger.info(f"Getting item with item_id {item_id}")

        result = await self.repo.get_item(item_id)

        if result.status == 'success':
            logger.info(
                LOG_ITEM_RETRIEVED,
                extra={
                    "item_id": result.data.item_id if hasattr(result.data, 'item_id') else None
                }
            )
        elif result.error_code == ERROR_CODE_ITEM_NOT_FOUND:
            logger.error(
                ERROR_ITEM_NOT_FOUND,
                extra={
                    "error_code": result.error_code,
                    "error_details": result.data
                }
            )
            raise NotFoundException(detail=result.message)


        return StandardResponse(
            status=result.status,
            message=result.message,
            data=result.data.to_dict()
        )

    @log_performance_async(threshold_ms=200)
    async def update_item(self, item: ItemCreate,
                                        item_id: str) -> StandardResponse:

        result = await self.repo.update_item(item, item_id)

        if result.status == 'success':
            # Invalidate the cache for this user's profile
            await invalidate_cache("item", item_id)
            logger.info(
                LOG_ITEM_UPDATED,
                extra={
                    "item_id": result.data.item_id if hasattr(result.data, 'item_id') else None
                }
            )
        elif result.error_code == ERROR_CODE_ITEM_NOT_FOUND:
            logger.error(
                ERROR_ITEM_NOT_FOUND,
                extra={
                    "error_code": result.error_code,
                    "error_details": result.data
                }
            )
            raise NotFoundException(detail=result.message)


        return StandardResponse(
            status=result.status,
            message=result.message,
            data=result.data.to_dict()
        )

    @log_performance_async(threshold_ms=200)
    async def delete_item(self, item_id: str) -> StandardResponse:
        result = await self.repo.delete_item(item_id)

        if result.status == "success":
            await invalidate_cache("item", item_id)
            logger.info(
                LOG_ITEM_DELETED,
                extra={
                    "item_id": result.data.item_id if hasattr(result.data, 'item_id') else None
                }
            )

        return StandardResponse(
            status=result.status,
            message=result.message,
            data=result.data.to_dict()
        )