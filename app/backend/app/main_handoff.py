from fastapi import FastAPI
from .routers.simple_chat import chat_routers_handoff,auth_routers, content_routers
from app.config.settings import settings
from app.config.logging import get_logger, setup_logging
from app.config.container_azure_chat import Container
from azure.monitor.opentelemetry import configure_azure_monitor
from agent_framework.observability import create_resource, enable_instrumentation


enable_instrumentation()

# Azure Chat based dependency injection container




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
    container.wire(modules=[chat_routers_handoff,content_routers])
    
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
    app.include_router(auth_routers.router, prefix="/api", tags=["auth"])
    app.include_router(chat_routers_handoff.router, prefix="/api", tags=["chat"])
    app.include_router(content_routers.router, prefix="/api", tags=["content"])


    logger.info("FastAPI application created successfully")
    return app


app = create_app()
