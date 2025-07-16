from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import time
from opentelemetry import trace

from configuration.config import get_app_settings, get_redis_settings
from database.sqlalchemy_connect import create_tables, engine
from utils.cache import redis_client, async_redis_client
from utils.telemetry import configure_telemetry, tracer, meter
from utils.logger import logger
from api import item
from health import health_check, metrics_router
from exceptions_handler import (ConflictException, DatabaseException, InvalidCredentialsException, NotFoundException,
                                UnexpectedException,
                                BadRequestException, NotAuthorizedException, DatabaseIntegrityException)

redis_settings = get_redis_settings()
app_settings = get_app_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables(engine)

    try:
        # Use the async Redis client for ping
        await async_redis_client.ping()
        logger.info("Redis cache connection established")
    except Exception as e:
        logger.warning(f"Redis cache connection failed: {str(e)}. Caching will be bypassed.")

    logger.info("App is Running", extra={"environment": app_settings.ENVIRONMENT})
    yield

    # Close Redis connections on shutdown
    try:
        # Close the synchronous client
        redis_client.close()
        # Close the asynchronous client
        await async_redis_client.close()
        logger.info("Redis cache connections closed")
    except Exception as e:
        logger.warning(f"Error closing Redis connections: {str(e)}")

app = FastAPI(
    lifespan=lifespan,
    title="Item App",
    description="Simple Item API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    root_path="/",
    debug=app_settings.DEBUG
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SKIP_PATHS = {
    "/health",
    "/metrics",
    "/static",
    "/favicon.ico"
}

app.include_router(item.router, prefix="/api/v1/item", tags=["Item"])
app.include_router(health_check.router, tags=["Health"])
app.include_router(metrics_router, tags=["Metrics"])

# Configurer OpenTelemetry avec l'application FastAPI
configure_telemetry(app)


@app.middleware("http")
async def request_middleware(request: Request, call_next: Callable):
    path = request.url.path
    method = request.method
    request_id = request.headers.get("X-Request-ID", "")

    # Create metrics counters if they don't exist yet
    # These will be created only once and reused for subsequent requests
    if not hasattr(request_middleware, "request_counter"):
        request_middleware.request_counter = meter.create_counter(
            name="http.server.request.count",
            description="Total number of HTTP requests",
            unit="1"
        )

    if not hasattr(request_middleware, "request_duration"):
        request_middleware.request_duration = meter.create_histogram(
            name="http.server.request.duration",
            description="Duration of HTTP requests",
            unit="s"
        )

    # Ignorer la journalisation pour les chemins qui n'en ont pas besoin
    if any(path.startswith(skip) for skip in SKIP_PATHS):
        return await call_next(request)

    # Toujours journaliser le temps de requête pour la surveillance des performances
    start_time = time.time()

    # Définir le contexte de journal standard pour cette requête
    log_context = {
        "request_id": request_id,
        "method": method,
        "path": path
    }

    # Record the request in metrics
    request_middleware.request_counter.add(1, {"method": method, "path": path})

    # Créer un span pour la requête
    with tracer.start_as_current_span(f"{method} {path}", attributes=log_context) as span:
        try:
            response = await call_next(request)

            # Calculer la durée de la requête
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)

            # Record the request duration in metrics
            request_middleware.request_duration.record(
                process_time, 
                {"method": method, "path": path, "status_code": str(response.status_code)}
            )

            # Ajouter le timing et le statut au contexte de journal
            log_context.update({
                "status_code": response.status_code,
                "process_time": process_time,
            })

            # Ajouter des attributs au span
            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("http.duration", process_time)

            # Journaliser uniquement les réponses lentes ou d'erreur pour réduire le volume de journaux
            if process_time > 0.5:
                logger.warn(
                    f"Réponse lente : {process_time}",
                    extra=log_context
                )

            return response

        except Exception as e:
            # Toujours journaliser les exceptions
            process_time = time.time() - start_time
            log_context.update({
                "process_time": process_time,
                "error_type": e.__class__.__name__
            })

            # Marquer le span comme en erreur
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))

            logger.exception(e, "Le traitement de la requête a échoué", extra=log_context)
            raise

@app.exception_handler(RequestValidationError)
async def custom_validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),  # e.g., "body.name" or "query.param"
            "message": error["msg"],  # Human-readable error message
            "type": error["type"]  # Error type (e.g., "type_error.integer")
        })

    # Use structured logging with minimal details
    logger.error(
        "Request validation error",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error_count": len(errors),
            "first_error": errors[0] if errors else None
        }
    )

    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "Validation failed",
            "errors": errors
        },
    )


@app.exception_handler(ResponseValidationError)
async def custom_response_validation_exception_handler(request: Request, exc: ResponseValidationError):
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    # Only log the count and first error in production
    logger.error(
        "Response validation error",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error_count": len(errors),
            "first_error": errors[0] if errors else None
        }
    )

    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "Validation failed",
            "errors": errors
        },
    )


@app.exception_handler(UnexpectedException)
def something_went_wrong_exception(req: Request, ex: UnexpectedException):
    return JSONResponse(status_code=ex.status_code,
                        content={"message": f"{ex.detail}", "status": "failed", "data": None})


@app.exception_handler(BadRequestException)
def bad_request_exception(req: Request, ex: BadRequestException):
    return JSONResponse(status_code=ex.status_code,
                        content={"message": f"{ex.detail}", "status": "failed", "data": None})


@app.exception_handler(NotAuthorizedException)
def not_authorized_exception(req: Request, ex: NotAuthorizedException):
    return JSONResponse(status_code=ex.status_code,
                        content={"message": f"{ex.detail}", "status": "failed", "data": None})


@app.exception_handler(NotFoundException)
def not_found_exception(req: Request, ex: NotFoundException):
    return JSONResponse(status_code=ex.status_code,
                        content={"message": f"{ex.detail}", "status": "failed", "data": None})

@app.exception_handler(ConflictException)
def conflict_exception(req: Request, ex: ConflictException):
    return JSONResponse(status_code=ex.status_code,
                        content={"message": f"{ex.detail}", "status": "failed", "data": None})


@app.exception_handler(InvalidCredentialsException)
def conflict_exception(req: Request, ex: InvalidCredentialsException):
    return JSONResponse(status_code=ex.status_code,
                        content={"message": f"{ex.detail}", "status": "failed", "data": None})


@app.exception_handler(DatabaseException)
def database_exception(req: Request, ex: DatabaseException):
    return JSONResponse(status_code=ex.status_code,
                        content={"message": f"{ex.detail}", "status": "failed", "data": None})


@app.exception_handler(DatabaseIntegrityException)
def database_integrity_exception(req: Request, ex: DatabaseIntegrityException):
    return JSONResponse(status_code=ex.status_code,
                        content={"message": f"{ex.detail}", "status": "failed", "data": None})


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000)
