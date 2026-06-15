import logging

import torch
import torch.nn.functional as F
import torchvision.models as tv_models

from src.config import settings
from src.utils import setup_logging

logger = logging.getLogger(__name__)


class ModelWrapper:
    def __init__(self) -> None:
        self._model = None
        self._loaded = False
        self._categories = None
        self._transforms = None

    def load(self) -> None:
        setup_logging(settings.LOG_LEVEL)
        weights = tv_models.ResNet18_Weights.IMAGENET1K_V1
        self._model = tv_models.resnet18(weights=weights)
        self._categories = weights.meta["categories"]
        self._transforms = weights.transforms()
        self._model = self._model.to(settings.DEVICE)
        self._model.eval()
        self._loaded = True
        logger.info("ResNet18 loaded on %s", settings.DEVICE)

    def predict(self, image, top_k: int = 5) -> dict:
        if not self._loaded:
            raise RuntimeError("Model not loaded")
        tensor = self._transforms(image).unsqueeze(0).to(settings.DEVICE)
        with torch.no_grad():
            logits = self._model(tensor)
        probs = F.softmax(logits, dim=1)
        values, indices = torch.topk(probs, top_k)
        return {
            "predictions": [
                {
                    "class": self._categories[idx],
                    "probability": float(prob),
                }
                for idx, prob in zip(indices[0].tolist(), values[0].tolist())
            ]
        }

    def is_loaded(self) -> bool:
        return self._loaded


model = ModelWrapper()
