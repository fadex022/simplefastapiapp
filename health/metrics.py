"""
Metrics module for the application
Provides endpoints for exposing OpenTelemetry metrics.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette.responses import JSONResponse
from starlette.status import HTTP_200_OK
from typing import Dict, Any, Coroutine
import time

# Create router
router = APIRouter(tags=["Metrics"])

# Store start time for uptime calculation
START_TIME = time.time()

@router.get("/metrics", 
            summary="Metrics endpoint",
            description="Exposes application metrics in JSON format")
async def metrics() -> JSONResponse:
    """
    Metrics endpoint - Returns basic application metrics in JSON format.
    Used by monitoring systems to scrape metrics.

    This is a simple implementation that returns basic metrics.
    In a production environment, you would use a more robust solution
    like Prometheus or the OpenTelemetry Collector.
    """
    # Calculate uptime
    uptime_seconds = time.time() - START_TIME

    # Return basic metrics
    return JSONResponse(
        content={
            "app_metrics": {
                "service_name": "simplefastapiapp",
                "uptime_seconds": uptime_seconds,
                "status": "running"
            },
            "message": "OpenTelemetry metrics are being sent to the configured OTLP endpoint"
        },
        status_code=HTTP_200_OK
    )
