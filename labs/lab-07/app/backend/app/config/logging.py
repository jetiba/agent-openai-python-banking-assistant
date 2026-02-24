import logging
import logging.config
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

from app.config.settings import settings


def get_logging_config_path(profile: Optional[str] = None) -> Optional[Path]:
    """Get the path to the logging configuration file based on the profile."""
    if profile is None:
        profile = os.getenv("PROFILE")
        if profile is None:
            print("No PROFILE environment variable set, using default logging configuration.")
            return Path(__file__).parent.parent.joinpath("logging-default.yaml")

    print(f"App profile is: {profile}")

    config_dir = Path(__file__).parent.parent

    profile_config = config_dir.joinpath(f"logging-{profile}.yaml")
    default_config = config_dir.joinpath("logging-default.yaml")

    if profile_config.exists():
        return profile_config
    elif default_config.exists():
        return default_config
    else:
        return None


def load_logging_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load logging configuration from YAML file."""
    if config_path is None:
        config_path = get_logging_config_path()

    if config_path is None or not config_path.exists():
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "INFO",
                    "formatter": "default",
                    "stream": "ext://sys.stdout"
                }
            },
            "root": {
                "level": "INFO",
                "handlers": ["console"]
            }
        }

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"Error loading logging config from {config_path}: {e}")
        return load_logging_config()


def setup_logging(profile: Optional[str] = None) -> None:
    """Setup logging configuration based on the profile."""
    config_path = get_logging_config_path(profile)
    config = load_logging_config(config_path)

    try:
        logging.config.dictConfig(config)
        if config_path:
            print(f"Logging configured from: {config_path}")
        else:
            print("Logging configured with default settings")
    except Exception as e:
        print(f"Error configuring logging: {e}")
        logging.basicConfig(level=logging.INFO)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance."""
    if name is None:
        import inspect
        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get('__name__', 'app')
        else:
            name = 'app'

    return logging.getLogger(name)
