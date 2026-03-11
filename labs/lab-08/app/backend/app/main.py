from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat_routers, attachment_routers
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
    if settings.APPLICATIONINSIGHTS_CONNECTION_STRING:
        configure_azure_monitor(
            connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING,
            resource=create_resource(),
            enable_live_metrics=True,
        )
    else:
        logger.info("APPLICATIONINSIGHTS_CONNECTION_STRING not set — Azure Monitor disabled.")

    logger.info(f"Creating FastAPI application: {settings.APP_NAME}")
    app = FastAPI(title=settings.APP_NAME)

    # Initialize dependency injection container
    container = Container()
    # Only attachment_routers uses DI injection (Depends/Provide for blob_proxy);
    # chat_routers uses the direct singleton pattern.
    container.wire(modules=[attachment_routers])
    app.state.container = container

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        logger.info("Shutting down application...")
        container.unwire()

    app.router.lifespan_context = lifespan

    app.include_router(chat_routers.router, tags=["chat"])
    app.include_router(attachment_routers.router, tags=["attachments"])

    logger.info("FastAPI application created successfully")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


app = create_app()
