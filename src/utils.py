import io
import json
import logging
from datetime import datetime, timezone

import requests
from PIL import Image

from src.config import settings


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": datetime.fromtimestamp(
                    record.created, tz=timezone.utc
                ).isoformat(),
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
            }
        )


def setup_logging(level: str) -> None:
    if logging.root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    logging.root.addHandler(handler)
    logging.root.setLevel(level)


def download_image(url: str) -> Image.Image:
    response = requests.get(url, stream=True, timeout=10)
    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        raise ValueError(f"Expected image content-type, got: {content_type!r}")
    max_bytes = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
    data = bytearray()
    for chunk in response.iter_content(chunk_size=8192):
        data.extend(chunk)
        if len(data) > max_bytes:
            raise ValueError(
                f"Image exceeds {settings.MAX_IMAGE_SIZE_MB} MB maximum size"
            )
    return Image.open(io.BytesIO(bytes(data))).convert("RGB")
