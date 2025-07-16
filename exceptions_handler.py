from fastapi import HTTPException

class NotAuthorizedException(HTTPException):
    def __init__(self, detail: str = "Not Authorized", **kwargs):
        super().__init__(status_code=401, detail=detail)

class UnexpectedException(HTTPException):
    def __init__(self, detail: str = "Something Went Wrong", **kwargs):
        super().__init__(status_code=500, detail=detail)

class BadRequestException(HTTPException):
    def __init__(self, detail: str = "Bad Request", **kwargs):
        super().__init__(status_code=400, detail=detail)

class NotFoundException(HTTPException):
    def __init__(self, detail: str = "Not Found", **kwargs):
        super().__init__(status_code=404, detail=detail)

class ConflictException(HTTPException):
    def __init__(self, detail: str = "Conflict", **kwargs):
        super().__init__(status_code=409, detail=detail)

class InvalidCredentialsException(HTTPException):
    def __init__(self, detail: str, headers: dict[str, str] | None = None):
        super().__init__(status_code=401, detail=detail, headers=headers)

class DatabaseException(HTTPException):
    def __init__(self, detail: str = "The is an error, retry later", **kwargs):
        super().__init__(status_code=500, detail=detail)

class DatabaseIntegrityException(HTTPException):
    def __init__(self, detail: str = "The is an error, retry later", **kwargs):
        super().__init__(status_code=500, detail=detail)