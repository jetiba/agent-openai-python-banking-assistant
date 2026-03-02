import os
import logging
from logging_config import configure_logging
from mcp_tools import mcp
from fastapi import FastAPI
from routers import router as payment_routers
import uvicorn

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    # Initialize logging for the app
    configure_logging()
    logger = logging.getLogger(__name__)

    # Add MCP server to the FastAPI app
    mcp_app = mcp.http_app(path="/")
    app = FastAPI(title="Payment API and MCP server", lifespan=mcp_app.lifespan)
    app.mount("/mcp", mcp_app)

    # Include the payment REST router
    app.include_router(payment_routers, prefix="/api", tags=["payments"])

    logger.info("FastAPI application created successfully")
    return app


app = create_app()

if __name__ == "__main__":
    profile = os.environ.get("PROFILE", "prod")
    port = 8071 if profile == "dev" else 8080
    logger.info("Starting payment service server with profile: %s, port: %s", profile, port)
    uvicorn.run("main:app", host="0.0.0.0", port=port)
