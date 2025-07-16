from exceptions_handler import DatabaseException, DatabaseIntegrityException, UnexpectedException
from utils.make_repo_response import make_repo_response
from utils.logger import logger

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from functools import wraps

def handle_repo_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except IntegrityError as ie:
            await args[0].sess.rollback()
            if "unique constraint" in str(ie):
                result = make_repo_response("error", "DUPLICATE_ENTITY", "Duplicate entity", str(ie))
                logger.error(f"{result.message}",
                             extra={"error_code": result.error_code, "details": result.message})
                raise DatabaseIntegrityException(detail=result.message)
            result = make_repo_response("error", "INTEGRITY_ERROR", "Integrity error occurred", str(ie))
            logger.error(f"{result.message}",
                             extra={"error_code": result.error_code, "details": result.message})
            raise DatabaseIntegrityException(detail=result.message)
        except SQLAlchemyError as se:
            await args[0].sess.rollback()
            result =  make_repo_response("error", "DATABASE_ERROR", "Database error occurred", str(se))
            logger.error(f"{result.message}", 
                             extra={"error_code": result.error_code, "details": result.message})
            raise DatabaseException(detail=result.message)
        except Exception as e:
            await args[0].sess.rollback()
            result = make_repo_response("error", "UNEXPECTED_ERROR", "Unexpected error occurred", str(e))
            logger.error(f"{result.message}",
                             extra={"error_code": result.error_code, "details": result.message})
            raise UnexpectedException(detail=result.message)
    return wrapper