"""Structured logging configuration with PHI redaction."""

import os
import sys
import structlog
from typing import Any


def configure_logging(
    level: str = "INFO",
    format_type: str = "json",
    redact_phi: bool = True,
) -> None:
    """Configure structured logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: "json" or "text"
        redact_phi: Whether to redact PHI in log fields
    """
    # Configure standard library logging
    import logging
    
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )
    
    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if redact_phi:
        processors.append(redact_phi_processor)
    
    if format_type == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def redact_phi_processor(logger: Any, method_name: str, event_dict: dict) -> dict:
    """Processor to redact PHI from log fields.
    
    Redacts fields that may contain PHI:
    - patient_id, patient_name, ssn
    - tax_id, npi (sometimes)
    - addresses, phone numbers
    - Any field containing "name", "address", "phone", "ssn", "dob"
    """
    phi_keywords = ["name", "address", "phone", "ssn", "dob", "tax_id", "patient_id"]
    max_length = int(os.getenv("MAX_LOG_FIELD_LENGTH", "50"))
    
    for key, value in event_dict.items():
        key_lower = key.lower()
        
        # Check if key might contain PHI
        if any(keyword in key_lower for keyword in phi_keywords):
            if isinstance(value, str) and len(value) > 0:
                # Redact: show first 2 and last 2 characters, mask the rest
                if len(value) > 4:
                    event_dict[key] = value[:2] + "*" * min(len(value) - 4, 10) + value[-2:]
                else:
                    event_dict[key] = "****"
            elif value is not None:
                event_dict[key] = "****"
        
        # Truncate long values
        elif isinstance(value, str) and len(value) > max_length:
            event_dict[key] = value[:max_length] + "..."
    
    return event_dict


# Initialize logging on import
configure_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format_type=os.getenv("LOG_FORMAT", "json"),
    redact_phi=os.getenv("REDACT_PHI_IN_LOGS", "true").lower() == "true",
)

