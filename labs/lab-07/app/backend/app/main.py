from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat_routers
from app.config.settings import settings
from app.config.logging import get_logger, setup_logging
from azure.monitor.opentelemetry import configure_azure_monitor
from agent_framework.observability import create_resource, enable_instrumentation

enable_instrumentation()

from app.config.container import Container


def create_app() -> FastAPI:
    # Initialize logging for the app
    setup_logging()
    # Get logger for this module
    logger = get_logger(__name__)

    # Setup agent framework observability
    configure_azure_monitor(
        connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING,
        resource=create_resource(),
        enable_live_metrics=True,
    )

    logger.info(f"Creating FastAPI application: {settings.APP_NAME}")

    app = FastAPI(title=settings.APP_NAME)

    # Initialize dependency injection container
    container = Container()

    # Wire dependencies to modules that need them
    container.wire(modules=[chat_routers])

    # Store container in app state for potential cleanup
    app.state.container = container

    # Use FastAPI lifespan for startup and shutdown events
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        logger.info("Shutting down application...")
        container.unwire()

    app.router.lifespan_context = lifespan

    # Include routers
    app.include_router(chat_routers.router, tags=["chat"])

    logger.info("FastAPI application created successfully")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify exact origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


app = create_app()
