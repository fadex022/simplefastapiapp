from pydantic import BaseModel, Field
from typing import Any

class StandardResponse(BaseModel):
    data: dict[str, Any] | None = Field(default=None)
    status: str = Field(default="success")
    message: str = Field(default=None)

    def to_dict(self):
        return {
            "data": self.data,
            "status": self.status,
            "message": self.message
        }