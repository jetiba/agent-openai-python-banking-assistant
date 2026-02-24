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
    setup_logging()
    logger = get_logger(__name__)

    configure_azure_monitor(
        connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING,
        resource=create_resource(),
        enable_live_metrics=True,
    )

    logger.info(f"Creating FastAPI application: {settings.APP_NAME}")
    app = FastAPI(title=settings.APP_NAME)

    container = Container()
    container.wire(modules=[chat_routers, attachment_routers])
    app.state.container = container

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        logger.info("Shutting down...")
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
