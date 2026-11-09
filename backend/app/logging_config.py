"""Structured JSON logs on stderr (Cloud Logging parses them). One line per request, built from method, path,
status and duration only: query strings (OAuth `code`/`state`), cookies and headers are never logged."""
import json
import logging
import sys
from datetime import datetime, timezone

# Cloud Logging severity names.
_SEVERITY = {"WARNING": "WARNING", "ERROR": "ERROR", "CRITICAL": "CRITICAL", "INFO": "INFO", "DEBUG": "DEBUG"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "severity": _SEVERITY.get(record.levelname, "DEFAULT"),
            "logger": record.name,
            "message": record.getMessage(),
        }
        out.update(getattr(record, "fields", {}))
        if record.exc_info:
            out["exception"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


class _StderrHandler(logging.StreamHandler):
    @property
    def stream(self):  # resolve at write time so redirected/captured stderr is honoured
        return sys.stderr

    @stream.setter
    def stream(self, _):
        pass


def configure_logging() -> None:
    handler = _StderrHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers, lg.propagate = [], True  # same JSON handler as everything else
    # uvicorn's access log prints the full URL incl. query string; the request middleware replaces it.
    access = logging.getLogger("uvicorn.access")
    access.handlers, access.propagate, access.disabled = [], False, True
    logging.getLogger("alembic").setLevel(logging.WARNING)  # plugin-setup chatter on every start
    # httpx logs full request URLs at INFO, which can carry API keys.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
