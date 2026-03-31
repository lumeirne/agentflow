"""Structured JSON logger with token redaction."""

import json
import logging
import sys
from datetime import datetime, timezone

from backend.utils.redaction import redact_dict


class RedactingFormatter(logging.Formatter):
    """JSON formatter that redacts sensitive values."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include extra fields if present
        if hasattr(record, "data") and isinstance(record.data, dict):
            log_entry["data"] = redact_dict(record.data)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def get_logger(name: str) -> logging.Logger:
    """Create a structured logger with redaction."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(RedactingFormatter())
        logger.addHandler(handler)
        # Use DEBUG to capture detailed matching diagnostics
        logger.setLevel(logging.DEBUG)

    return logger
