from datetime import date
from typing import Annotated
from fastapi import APIRouter, Depends, Request, Form, Security, UploadFile
from models.response.StandardResponse import StandardResponse

from models.request.item import ItemCreate 
from service.item import ItemService

router = APIRouter()



@router.post("/create-item", status_code=201, response_model=StandardResponse)
async def create_item(item: ItemCreate, item_service: ItemService = Depends(ItemService)):
    return await item_service.create_item(item)

@router.get("/get-item/{item_id}", response_model=StandardResponse)
async def get_item(item_id: str, item_service: ItemService = Depends(ItemService)):
    return await item_service.get_item(item_id)

@router.put("/update-item/{item_id}", response_model=StandardResponse)
async def update_item(item_id: str, item: ItemCreate, item_service: ItemService = Depends(ItemService)):
    return await item_service.update_item(item, item_id)

@router.delete("/delete-item/{item_id}", response_model=StandardResponse)
async def delete_item(item_id: str, item_service: ItemService = Depends(ItemService)):
    return await item_service.delete_item(item_id)