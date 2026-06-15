import io
import logging
import unittest.mock

import pytest
import requests
from PIL import Image

from src.utils import download_image, setup_logging


def _make_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="JPEG")
    return buf.getvalue()


def _mock_response(content_type: str, chunks: list) -> unittest.mock.MagicMock:
    mock_resp = unittest.mock.MagicMock()
    mock_resp.headers = {"content-type": content_type}
    mock_resp.iter_content.return_value = iter(chunks)
    return mock_resp


# --- download_image ---


@unittest.mock.patch("requests.get")
def test_download_image_happy_path(mock_get):
    jpeg_bytes = _make_jpeg_bytes()
    mock_get.return_value = _mock_response("image/jpeg", [jpeg_bytes])
    result = download_image("http://example.com/image.jpg")
    assert isinstance(result, Image.Image)
    assert result.mode == "RGB"


@unittest.mock.patch("requests.get")
def test_download_image_bad_content_type_raises(mock_get):
    mock_get.return_value = _mock_response("text/html", [b"<html></html>"])
    with pytest.raises(ValueError, match="content-type"):
        download_image("http://example.com/notanimage")


@unittest.mock.patch("requests.get")
def test_download_image_oversized_raises(mock_get):
    oversized_chunk = b"x" * (6 * 1024 * 1024)  # 6 MB > MAX_IMAGE_SIZE_MB=5
    mock_get.return_value = _mock_response("image/jpeg", [oversized_chunk])
    with pytest.raises(ValueError, match="maximum size"):
        download_image("http://example.com/huge.jpg")


@unittest.mock.patch("requests.get")
def test_download_image_timeout_propagates(mock_get):
    mock_get.side_effect = requests.exceptions.Timeout
    with pytest.raises(requests.exceptions.Timeout):
        download_image("http://example.com/slow.jpg")


# --- setup_logging ---


def test_setup_logging_sets_level():
    logging.root.handlers.clear()
    setup_logging("DEBUG")
    assert logging.root.level == logging.DEBUG
    logging.root.handlers.clear()


def test_setup_logging_is_idempotent():
    logging.root.handlers.clear()
    setup_logging("WARNING")
    setup_logging("WARNING")
    assert len(logging.root.handlers) == 1
    logging.root.handlers.clear()
