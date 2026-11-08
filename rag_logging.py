"""Content-free operational events: one JSON line per measured operation."""
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from time import perf_counter


logger = logging.getLogger("rag.operations")
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.propagate = False


@contextmanager
def log_operation(operation):
    started = perf_counter()
    outcome = {"status": "ok"}
    error_type = None
    try:
        yield outcome
    except Exception as exc:
        if isinstance(exc, PermissionError):
            outcome["status"] = "denied"
        elif isinstance(exc, (ValueError, UnicodeError)):
            outcome["status"] = "invalid"
        else:
            outcome["status"] = "error"
        # A provider exception message can contain the actual request.
        error_type = type(exc).__name__
        raise
    finally:
        logger.log(
            logging.ERROR if outcome["status"] == "error" else logging.INFO,
            json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "operation": operation,
                "status": outcome["status"],
                "error_type": error_type,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            }),
        )
