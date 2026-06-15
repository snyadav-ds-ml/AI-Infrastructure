# Spec: Utils

## Overview
This step implements the utility helpers in `src/utils.py` that the rest of the application depends
on. Specifically: `download_image()` fetches an image from a URL (enforcing size limits and
content-type validation) and returns a `PIL.Image`, while `setup_logging()` configures structured
JSON logging for the entire process. Getting these right early is critical — the API endpoint and
model wrapper both call `download_image()` on every prediction request, and every component depends
on consistent logging. Implementing this before the model wrapper (T2) and API (T3) ensures no
caller has to work around a `NotImplementedError`.

## Depends on
- **Step 00 — Directory Setup**: provides the file skeleton, `requirements.txt` with `requests` and
  `Pillow` already pinned, and `src/__init__.py` so the package resolves.
- **`src/config.py`** must already define `settings.MAX_IMAGE_SIZE_MB` and `settings.LOG_LEVEL`
  (both are present from step 00).

## Routes
No new routes.

## Templates
- **Create:** None (backend-only step)
- **Modify:** None

## Files to change
- `src/utils.py` — replace the two stubs with full implementations

## Files to create
- `tests/test_utils.py` — replace the single placeholder assertion with real unit tests

## New dependencies
No new pip installs. `requests`, `Pillow`, and the standard-library `logging`/`json` modules are
already in `requirements.txt` and the `ai-infra` conda environment.

## Implementation notes

### `download_image(url: str) -> PIL.Image.Image`
1. Send a `requests.get(url, stream=True, timeout=10)` — `timeout` prevents hanging on slow servers.
2. Validate `Content-Type` header starts with `image/`; raise `ValueError` with a clear message if not.
3. Read the body in chunks, accumulating bytes. Stop and raise `ValueError` if accumulated size
   exceeds `settings.MAX_IMAGE_SIZE_MB * 1024 * 1024`.
4. Wrap raw bytes in `io.BytesIO` and return `PIL.Image.open(...).convert("RGB")`.
5. Let `requests.Timeout` and `requests.RequestException` propagate — callers handle these.

### `setup_logging(level: str) -> None`
1. Configure the root logger at the specified level (e.g. `"INFO"`, `"DEBUG"`).
2. Replace the default `StreamHandler` formatter with a `logging.Formatter` that emits one JSON
   object per line: `{"timestamp": ..., "level": ..., "name": ..., "message": ...}`.
3. Call once at application startup (idempotent — guard with a module-level `_configured` flag or
   `logging.root.handlers` check to avoid duplicate handlers in tests).

## Definition of done
- [ ] `from src.utils import download_image, setup_logging` imports without error
- [ ] `setup_logging("INFO")` runs without error; subsequent `logging.info("x")` emits a
      parseable JSON line to stderr
- [ ] `download_image()` with a valid public image URL (e.g. a small JPEG) returns a
      `PIL.Image.Image` in RGB mode
- [ ] `download_image()` raises `ValueError` when the server returns a non-image `Content-Type`
- [ ] `download_image()` raises `ValueError` when the response body exceeds `MAX_IMAGE_SIZE_MB`
- [ ] `download_image()` raises `requests.exceptions.Timeout` when the server does not respond
      within 10 seconds (mock with `unittest.mock.patch`)
- [ ] `pytest tests/test_utils.py -v` collects ≥ 4 tests and all pass
- [ ] `black --check src/utils.py tests/test_utils.py` passes with zero violations
- [ ] `flake8 src/utils.py tests/test_utils.py` passes with zero violations
