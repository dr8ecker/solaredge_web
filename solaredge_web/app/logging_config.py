"""Structured logs without raw browser exceptions, DOM or authentication data."""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Iterable


class SafeFormatter(logging.Formatter):
    def __init__(self, secrets: Iterable[str]):
        super().__init__()
        self.secrets = tuple(sorted((s for s in secrets if s), key=len, reverse=True))

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        for secret in self.secrets:
            message = message.replace(secret, "[redacted]")
        message = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted-email]", message)
        # URL query strings and fragments can contain authentication material.
        message = re.sub(r"(https?://[^\s?#]+)[?#][^\s]*", r"\1[redacted]", message)
        return json.dumps({
            "time": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": message,
        }, ensure_ascii=False)


def configure_logging(config) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(SafeFormatter((
        config.solar_edge_username, config.solar_edge_password,
        config.mqtt_username, config.mqtt_password,
    )))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if config.debug else logging.INFO)
    # Avoid verbose protocol output from dependencies even in debug mode.
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("websocket").setLevel(logging.WARNING)
