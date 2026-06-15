import unittest.mock

import pytest
import torch
from PIL import Image

from src.model import ModelWrapper


def _make_pil_image() -> Image.Image:
    return Image.new("RGB", (224, 224))


def _make_mock_weights():
    categories = [
        "tench",
        "goldfish",
        "great white shark",
        "tiger shark",
        "hammerhead shark",
    ] + [f"class_{i}" for i in range(995)]
    mock_transforms = unittest.mock.MagicMock()
    mock_transforms.return_value = torch.randn(3, 224, 224)
    mock_w = unittest.mock.MagicMock()
    mock_w.meta = {"categories": categories}
    mock_w.transforms.return_value = mock_transforms
    return mock_w


def _make_mock_model(logits=None):
    if logits is None:
        logits = torch.randn(1, 1000)
    mock_m = unittest.mock.MagicMock()
    mock_m.return_value = logits
    mock_m.to.return_value = mock_m
    return mock_m


def test_is_loaded_false_before_load():
    assert ModelWrapper().is_loaded() is False


def test_predict_raises_before_load():
    with pytest.raises(RuntimeError, match="Model not loaded"):
        ModelWrapper().predict(_make_pil_image())


@unittest.mock.patch("torchvision.models.resnet18")
@unittest.mock.patch("torchvision.models.ResNet18_Weights")
def test_load_sets_is_loaded(mock_weights_cls, mock_resnet18):
    mock_weights_cls.IMAGENET1K_V1 = _make_mock_weights()
    mock_resnet18.return_value = _make_mock_model()
    wrapper = ModelWrapper()
    wrapper.load()
    assert wrapper.is_loaded() is True


@unittest.mock.patch("torchvision.models.resnet18")
@unittest.mock.patch("torchvision.models.ResNet18_Weights")
def test_predict_returns_five_predictions(mock_weights_cls, mock_resnet18):
    mock_weights_cls.IMAGENET1K_V1 = _make_mock_weights()
    mock_resnet18.return_value = _make_mock_model()
    wrapper = ModelWrapper()
    wrapper.load()
    result = wrapper.predict(_make_pil_image())
    assert "predictions" in result
    assert len(result["predictions"]) == 5
    for item in result["predictions"]:
        assert isinstance(item["class"], str)
        assert isinstance(item["probability"], float)


@unittest.mock.patch("torchvision.models.resnet18")
@unittest.mock.patch("torchvision.models.ResNet18_Weights")
def test_predict_probabilities_descending(mock_weights_cls, mock_resnet18):
    logits = torch.zeros(1, 1000)
    logits[0, 0] = 10.0
    logits[0, 1] = 5.0
    logits[0, 2] = 3.0
    logits[0, 3] = 2.0
    logits[0, 4] = 1.0
    mock_weights_cls.IMAGENET1K_V1 = _make_mock_weights()
    mock_resnet18.return_value = _make_mock_model(logits=logits)
    wrapper = ModelWrapper()
    wrapper.load()
    preds = wrapper.predict(_make_pil_image())["predictions"]
    probs = [p["probability"] for p in preds]
    assert probs == sorted(probs, reverse=True)


@unittest.mock.patch("src.model.setup_logging")
@unittest.mock.patch("torchvision.models.resnet18")
@unittest.mock.patch("torchvision.models.ResNet18_Weights")
def test_load_calls_setup_logging(mock_weights_cls, mock_resnet18, mock_log):
    mock_weights_cls.IMAGENET1K_V1 = _make_mock_weights()
    mock_resnet18.return_value = _make_mock_model()
    ModelWrapper().load()
    mock_log.assert_called_once()
