from dataclasses import dataclass
from pathlib import Path

import torch
from PIL import Image
from torchvision import models, transforms

from src.settings import (
    CORRUPTION_MODEL_PATH,
    ML_BROKEN_THRESHOLD,
    ML_SUSPECT_THRESHOLD,
)


@dataclass
class MLClassificationResult:
    model_available: bool
    probability_broken: float
    status: str
    reason: str


_MODEL_CACHE = None


def classify_image_with_ml(image: Image.Image) -> MLClassificationResult:
    if not CORRUPTION_MODEL_PATH.exists():
        return MLClassificationResult(
            model_available=False,
            probability_broken=0.0,
            status="not_available",
            reason="ML classifier model not found. Hard checks only.",
        )

    model = get_model(CORRUPTION_MODEL_PATH)
    model.eval()

    tensor = build_transform()(image.convert("RGB")).unsqueeze(0)

    with torch.no_grad():
        logits = model(tensor)
        probabilities = torch.softmax(logits, dim=1)
        probability_broken = float(probabilities[0, 1].item())

    if probability_broken >= ML_BROKEN_THRESHOLD:
        return MLClassificationResult(
            model_available=True,
            probability_broken=probability_broken,
            status="broken",
            reason=f"ML classifier found very high corruption probability: {probability_broken:.2%}",
        )

    if probability_broken >= ML_SUSPECT_THRESHOLD:
        return MLClassificationResult(
            model_available=True,
            probability_broken=probability_broken,
            status="suspect",
            reason=f"ML classifier found suspicious corruption probability: {probability_broken:.2%}",
        )

    return MLClassificationResult(
        model_available=True,
        probability_broken=probability_broken,
        status="ok",
        reason=f"ML classifier probability looks safe: {probability_broken:.2%}",
    )


def get_model(model_path: Path) -> torch.nn.Module:
    global _MODEL_CACHE

    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    model = build_model()
    checkpoint = torch.load(model_path, map_location="cpu")
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    _MODEL_CACHE = model

    return model


def build_model() -> torch.nn.Module:
    model = models.mobilenet_v3_small(weights=None)
    input_features = model.classifier[3].in_features
    model.classifier[3] = torch.nn.Linear(input_features, 2)
    return model


def build_transform() -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )