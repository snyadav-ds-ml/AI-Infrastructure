# Spec: Model Setup

## Overview
This step implements the `ModelWrapper` class in `src/model.py`, replacing the two `NotImplementedError`
stubs with a working ResNet18 image classifier. `load()` downloads the pretrained ImageNet weights via
`torchvision` and moves the model to the configured device; `predict()` accepts a `PIL.Image`, runs the
full preprocessing → forward pass → postprocessing pipeline, and returns a ranked list of top-5
ImageNet class predictions with probabilities. Getting this right before Step 03 (API) is essential —
the API delegates all inference to `ModelWrapper`, and the health check returns 503 until `is_loaded()`
is `True`. This step also wires up `tests/test_model.py` with real unit tests.

## Depends on
- **Step 00 — Directory Setup**: provides `src/model.py` stub, `src/__init__.py`, `requirements.txt`
  with `torch` and `torchvision` pinned.
- **Step 01 — Utils**: `setup_logging()` is called during model load to emit structured JSON logs;
  `src/utils.py` must already be implemented.
- **`src/config.py`** must define `settings.MODEL_NAME`, `settings.DEVICE`, and `settings.LOG_LEVEL`
  (all present from Step 00).

## Routes
No new routes.

## Templates
- **Create:** None (backend-only step)
- **Modify:** None

## Files to change
- `src/model.py` — replace `load()` and `predict()` stubs with full implementations
- `tests/test_model.py` — replace the single placeholder assertion with real unit tests

## Files to create
No new files.

## New dependencies
No new pip installs. `torch`, `torchvision`, and `Pillow` are already in `requirements.txt` and the
`ai-infra` conda environment.

## Implementation notes

### `ModelWrapper.load() -> None`
1. Call `setup_logging(settings.LOG_LEVEL)` to ensure structured logs are active before anything else.
2. Load model via `torchvision.models.ResNet18_Weights.IMAGENET1K_V1` — the modern weights API
   provides both the model and the category names in one object:
   ```python
   weights = torchvision.models.ResNet18_Weights.IMAGENET1K_V1
   self._model = torchvision.models.resnet18(weights=weights)
   self._categories = weights.meta["categories"]   # list of 1000 class names
   self._transforms = weights.transforms()          # standard ImageNet preprocessing
   ```
3. Move model to device: `self._model = self._model.to(settings.DEVICE)`.
4. Set eval mode: `self._model.eval()`.
5. Set `self._loaded = True`.
6. Log an INFO message: `"ResNet18 loaded on <device>"`.
7. Let `RuntimeError` (e.g. unsupported device) propagate — callers handle it.

### `ModelWrapper.predict(image: PIL.Image.Image, top_k: int = 5) -> dict`
1. Guard: raise `RuntimeError("Model not loaded")` if `not self._loaded`.
2. Apply `self._transforms(image)` — returns a normalised `(3, 224, 224)` tensor.
3. Add batch dimension: `tensor.unsqueeze(0)`.
4. Move tensor to device.
5. Run inference inside `torch.no_grad()`.
6. Apply `torch.nn.functional.softmax(logits, dim=1)` to get probabilities.
7. Take `torch.topk(probs, top_k)` — values and indices.
8. Return:
   ```python
   {
       "predictions": [
           {"class": self._categories[idx], "probability": float(prob)}
           for idx, prob in zip(indices[0], values[0])
       ]
   }
   ```

### Device handling
- Valid values from `settings.DEVICE`: `"cpu"`, `"cuda"`, `"mps"` (Apple Silicon).
- No special-casing needed; `torch` raises a clear `RuntimeError` for unavailable devices.

## Definition of done
- [ ] `from src.model import ModelWrapper, model` imports without error
- [ ] `model.load()` runs without error; `model.is_loaded()` returns `True` afterwards
- [ ] `model.predict(image)` with a `PIL.Image` returns a dict with key `"predictions"` containing
      a list of 5 items, each with `"class"` (str) and `"probability"` (float)
- [ ] Probabilities in the returned list sum to ≤ 1.0 and are in descending order
- [ ] `model.predict(image)` raises `RuntimeError` when called before `model.load()`
- [ ] `setup_logging` is called during `load()` — subsequent log output is valid JSON
- [ ] `pytest tests/test_model.py -v` collects ≥ 5 tests and all pass
- [ ] `black --check src/model.py tests/test_model.py` passes with zero violations
- [ ] `flake8 src/model.py tests/test_model.py` passes with zero violations
