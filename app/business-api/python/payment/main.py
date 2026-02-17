import os
import logging
from logging_config import configure_logging
from keyvault_helper import verify_keyvault_access
from mcp_tools import mcp
from fastapi import FastAPI
from routers import router as payment_routers
import uvicorn

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    # Initialize logging for the app
    configure_logging()
    logger = logging.getLogger(__name__)

    # Verify Key Vault connectivity (non-blocking)
    verify_keyvault_access()

    # Add MCP server to the FastAPI app
    mcp_app = mcp.http_app(path="/mcp")
    app = FastAPI(title="Payment API and MCP server", lifespan=mcp_app.lifespan)
    app.mount("/mcp", mcp_app)

    # Include the payment REST router
    app.include_router(payment_routers, prefix="/api", tags=["payments"])

    logger.info("FastAPI application created successfully")
    return app


app = create_app()
