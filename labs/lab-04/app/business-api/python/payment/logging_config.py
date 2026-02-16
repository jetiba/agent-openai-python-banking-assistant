import logging
import os


def configure_logging(level: str = "INFO"):
    """Configure application logging with Azure Monitor OpenTelemetry when available.

    If APPLICATIONINSIGHTS_CONNECTION_STRING is set, the Azure Monitor
    OpenTelemetry distro is activated.  It auto-instruments the Python
    logging module, FastAPI / ASGI requests, and outgoing HTTP calls so
    that traces, metrics, and logs flow to Application Insights with no
    code changes elsewhere.

    Falls back to basic console logging when the connection string is
    absent (e.g., local development).
    """
    connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")

    if connection_string:
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor(
                connection_string=connection_string,
                logger_name="",                  # instrument root logger
                enable_live_metrics=True,
            )
            logging.getLogger(__name__).info(
                "Azure Monitor OpenTelemetry configured successfully"
            )
            return
        except ImportError:
            logging.getLogger(__name__).warning(
                "azure-monitor-opentelemetry not installed – "
                "falling back to basic logging"
            )
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning(
                "Failed to configure Azure Monitor: %s – "
                "falling back to basic logging",
                exc,
            )

    # Fallback: plain console logging
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
