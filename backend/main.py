"""
Main FastAPI Application Entry Point
Phase-1a: Social Media CRM Backend
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
import logging
from datetime import datetime, timezone
import uvicorn

# Configuration
from config import settings

# API Routes
from app.api import (
    auth,
    customers,
    dashboard,
    interactions,
    monitoring,
    platforms,
    responses,
    system_settings,
    tickets,
    users,
    webhooks,
)

# Database
from app.database import Base, engine, init_db

# Custom exceptions and middleware
from app.exceptions import CustomException
from middleware.logging_middleware import LoggingMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting Social Media CRM Backend")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

    # Initialize database
    try:
        init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {str(e)}")
        raise

    yield

    # Shutdown
    logger.info("🛑 Shutting down Social Media CRM Backend")


# Initialize FastAPI application
app = FastAPI(
    title="Social Media CRM API",
    description="Unified Social Media Handling CRM for Customer Engagement & Reputation Management",
    version="1.0.0-alpha",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ============================================================================
# MIDDLEWARE SETUP
# ============================================================================

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)

# Trusted Host Middleware
if not settings.DEBUG:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

# Custom Logging Middleware
app.add_middleware(LoggingMiddleware)

# ============================================================================
# ERROR HANDLERS
# ============================================================================


@app.exception_handler(CustomException)
async def custom_exception_handler(request, exc: CustomException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid request data",
            "details": jsonable_encoder(exc.errors()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": (
                "An unexpected error occurred" if not settings.DEBUG else str(exc)
            ),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================


@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0-alpha",
    }


@app.get("/api/health", tags=["Health"])
async def api_health_check():
    """API health check endpoint"""
    return {
        "status": "healthy",
        "service": "social-media-crm-api",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================================================
# API ROUTES REGISTRATION
# ============================================================================

# Auth Routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])

# User Management Routes
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])

# Platform Integration Routes
app.include_router(platforms.router, prefix="/api/v1", tags=["Platforms"])

# Interaction Routes
app.include_router(
    interactions.router, prefix="/api/v1/interactions", tags=["Interactions"]
)
app.include_router(monitoring.router, prefix="/api/v1/monitoring", tags=["Monitoring"])

# Ticket Routes
app.include_router(tickets.router, prefix="/api/v1/tickets", tags=["Tickets"])

# Response Routes
app.include_router(responses.router, prefix="/api/v1/responses", tags=["Responses"])

# Customer Routes
app.include_router(customers.router, prefix="/api/v1/customers", tags=["Customers"])

# Dashboard Routes
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])

# System Settings Routes
app.include_router(system_settings.router, prefix="/api/v1/settings", tags=["Settings"])

# Webhook Routes (no /api/v1 prefix for security)
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])

# ============================================================================
# ROOT ENDPOINT
# ============================================================================


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information"""
    return {
        "name": "Social Media CRM API",
        "version": "1.0.0-alpha",
        "environment": settings.ENVIRONMENT,
        "documentation": "/api/docs",
        "health": "/health",
    }


# ============================================================================
# STARTUP LOGGING
# ============================================================================

if __name__ == "__main__":
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Database URL: {settings.DATABASE_URL.split('@')[0]}...@...")

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
