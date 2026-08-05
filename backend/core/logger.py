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
        formatter = EIMSJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s %(pathname)s %(lineno)d'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Adjust logging threshold based on declarative Pydantic configs
        logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        logger.propagate = False
        
    return logger
