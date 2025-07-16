from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from enum import Enum
from datetime import date

class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1, max_length=500)
    price: float = Field(gt=0)
    
    model_config = ConfigDict (
        from_attributes= True,
        str_strip_whitespace= True,
        extra= 'forbid'
    )
