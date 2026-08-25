"""
==============================================================================
EIMS Structured JSON Logging Engine
Governed by EIMS Documentation System (EDS v1.0.0) - Prometheus/Loki Integration
==============================================================================
"""

import logging
import sys
from pythonjsonlogger import jsonlogger
from backend.core.config import settings
import os

try:
    import colorama
    colorama.init()
except ImportError:
    pass

class EIMSColoredFormatter(logging.Formatter):
    """Adds colors to local development logs for better readability."""
    COLORS = {
        'DEBUG': '\033[94m',      # Blue
        'INFO': '\033[92m',       # Green
        'WARNING': '\033[93m',    # Yellow
        'ERROR': '\033[91m',      # Red
        'CRITICAL': '\033[1;91m'  # Bold Red
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        record.name = f"\033[36m{record.name}{self.RESET}"
        return super().format(record)


class EIMSJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatting class augmenting standard system telemetry logs with
    mandatory timestamp indexing and explicit application environment tags.
    """
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        if not log_record.get("timestamp"):
            log_record["timestamp"] = record.created
        if log_record.get("level"):
            log_record["level"] = log_record["level"].upper()
        else:
            log_record["level"] = record.levelname
        log_record["service"] = "eims-core-gateway"
        log_record["environment"] = settings.ENVIRONMENT


def get_logger(module_name: str) -> logging.Logger:
    """
    Retrieves or instantiates an immutable logger emitting formatted JSON metrics
    standardized for continuous operational aggregation.
    """
    logger = logging.getLogger(module_name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        
        if settings.ENVIRONMENT == "development":
            formatter = EIMSColoredFormatter(
                '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        else:
            formatter = EIMSJsonFormatter(
                '%(timestamp)s %(level)s %(name)s %(message)s %(pathname)s %(lineno)d'
            )
            
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Adjust logging threshold based on declarative Pydantic configs
        logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        logger.propagate = False
        
    return logger
