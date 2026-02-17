import logging
import os
import sys


def _ensure_console_handler(level: int = logging.INFO):
    """Add a StreamHandler writing to stdout on the root logger (if not already present)."""
    root = logging.getLogger()
    root.setLevel(level)
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stdout:
            h.setLevel(level)
            return
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(fmt)
    root.addHandler(handler)


def configure_logging(level: str = "INFO"):
    """Configure application logging with Azure Monitor OpenTelemetry when available.

    A console StreamHandler is always added so that logs appear in
    container stdout regardless of Azure Monitor configuration.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")

    if connection_string:
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor(
                connection_string=connection_string,
                logger_name="",
                enable_live_metrics=True,
            )
        except ImportError:
            pass
        except Exception:  # noqa: BLE001
            pass

    _ensure_console_handler(log_level)

    # Suppress noisy Azure SDK loggers so app messages stay visible
    for _name in ("azure.core", "azure.monitor", "azure.identity"):
        logging.getLogger(_name).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging configured (console=True, azure_monitor=%s)",
        bool(connection_string),
    )
