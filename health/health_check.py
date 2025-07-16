"""
Health check module for the Auth Service
Provides endpoints and services for container orchestration health checks.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from enum import Enum
import time
import asyncio
from datetime import datetime

from database.sqlalchemy_connect import sess_db
from sqlalchemy import text
from utils.logger import logger
from utils.cache import async_cache_health_check

# Health status enum
class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"

# Health check response models
class DependencyHealth(BaseModel):
    name: str
    status: HealthStatus
    response_time_ms: float
    last_checked: datetime
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: HealthStatus
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.now)
    uptime_seconds: float
    dependencies: List[DependencyHealth]

# Create router
router = APIRouter(tags=["Health"])

# Service start time for uptime calculation
SERVICE_START_TIME = time.time()

# Health check functions
async def check_database_health(db_session: AsyncSession) -> DependencyHealth:
    """Check database connection health."""
    start_time = time.time()
    try:
        # Execute a simple query to verify database connection
        query = text("SELECT 1")
        await db_session.execute(query)

        elapsed_ms = (time.time() - start_time) * 1000
        return DependencyHealth(
            name="database",
            status=HealthStatus.HEALTHY,
            response_time_ms=elapsed_ms,
            last_checked=datetime.now()
        )
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(f"Database health check failed: {str(e)}")
        return DependencyHealth(
            name="database",
            status=HealthStatus.UNHEALTHY,
            response_time_ms=elapsed_ms,
            last_checked=datetime.now(),
            error=str(e)
        )

async def check_redis_cache_health() -> DependencyHealth:
    """Check Redis cache health."""
    start_time = time.time()
    try:
        # Check Redis connection using the async utility function
        is_healthy, message = await async_cache_health_check()

        elapsed_ms = (time.time() - start_time) * 1000
        status = HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY

        return DependencyHealth(
            name="redis_cache",
            status=status,
            response_time_ms=elapsed_ms,
            last_checked=datetime.now(),
            details={"message": message} if is_healthy else None,
            error=None if is_healthy else message
        )
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(f"Redis cache health check failed: {str(e)}")
        return DependencyHealth(
            name="redis_cache",
            status=HealthStatus.UNHEALTHY,
            response_time_ms=elapsed_ms,
            last_checked=datetime.now(),
            error=str(e)
        )

# Health check endpoints
@router.get("/health/live", status_code=status.HTTP_200_OK, response_model=Dict[str, str], 
             summary="Liveness probe",
             description="Simple health check to determine if the application is running")
async def liveness_check():
    """
    Liveness check - Returns a simple status to indicate the application is running.
    Used by container orchestration for liveness probes.
    """
    return {"status": "alive"}

@router.get("/health/ready", status_code=status.HTTP_200_OK, response_model=Dict[str, str],
            summary="Readiness probe",
            description="Basic readiness check to determine if the application is ready to receive traffic")
async def readiness_check(db_session: AsyncSession = Depends(sess_db)):
    """
    Readiness check - Performs a minimal check on the database to determine 
    if the application is ready to serve requests.
    Used by container orchestration for readiness probes.
    """
    try:
        # Quick database connection check
        query = text("SELECT 1")
        await db_session.execute(query)
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready"
        )

@router.get("/health", response_model=HealthResponse,
            summary="Comprehensive health check",
            description="Detailed health status of the application and its dependencies")
async def health_check(db_session: AsyncSession = Depends(sess_db)):
    """
    Comprehensive health check - Checks all dependencies and returns detailed status.
    """
    # Perform health checks in parallel
    db_health, redis_health = await asyncio.gather(
        check_database_health(db_session),
        check_redis_cache_health()
    )

    # Collect all dependency checks
    dependencies = [db_health, redis_health]

    # Determine overall status
    if any(dep.status == HealthStatus.UNHEALTHY for dep in dependencies):
        overall_status = HealthStatus.UNHEALTHY
    elif any(dep.status == HealthStatus.DEGRADED for dep in dependencies):
        overall_status = HealthStatus.DEGRADED
    else:
        overall_status = HealthStatus.HEALTHY

    # Calculate uptime
    uptime_seconds = time.time() - SERVICE_START_TIME

    # Create response
    response = HealthResponse(
        status=overall_status,
        uptime_seconds=uptime_seconds,
        dependencies=dependencies
    )

    # If health is not good, return appropriate status code
    if overall_status == HealthStatus.UNHEALTHY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.model_dump()
        )

    return response
