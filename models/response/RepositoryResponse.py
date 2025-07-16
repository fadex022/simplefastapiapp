from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Optional

class RepositoryResponse(BaseModel):
    status: str = Field(default="success")
    error_code: str = Field(default=None)
    message: str = Field(default=None)
    data: Optional[Any] = Field(default=None)

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        extra="forbid"
    )