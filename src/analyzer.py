from pathlib import Path

import cv2
import numpy as np

from src.models import ImageResult


def load_grayscale_image(path: Path) -> np.ndarray | None:
    try:
        raw_data = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None

    if raw_data.size == 0:
        return None

    return cv2.imdecode(raw_data, cv2.IMREAD_GRAYSCALE)


def calculate_entropy(image: np.ndarray) -> float:
    histogram = cv2.calcHist([image], [0], None, [256], [0, 256])
    probabilities = histogram.ravel() / image.size
    probabilities = probabilities[probabilities > 0]

    return float(-np.sum(probabilities * np.log2(probabilities)))


def calculate_dominant_pixel_ratio(image: np.ndarray) -> float:
    _, counts = np.unique(image, return_counts=True)
    return float(counts.max() / image.size)


def calculate_uniform_block_ratio(
    image: np.ndarray,
    block_size: int = 32,
    standard_deviation_limit: float = 1.5,
) -> float:
    height, width = image.shape

    total_blocks = 0
    uniform_blocks = 0

    for y in range(0, height, block_size):
        for x in range(0, width, block_size):
            block = image[y : y + block_size, x : x + block_size]

            if block.size == 0:
                continue

            total_blocks += 1

            if float(np.std(block)) <= standard_deviation_limit:
                uniform_blocks += 1

    if total_blocks == 0:
        return 0.0

    return uniform_blocks / total_blocks


def analyze_image(path: Path, result: ImageResult) -> None:
    image = load_grayscale_image(path)

    if image is None:
        return

    height, width = image.shape

    if width < 8 or height < 8:
        result.add_evidence(
            check="dimensions",
            passed=False,
            severity="review",
            message="La imagen tiene dimensiones extremadamente pequeñas.",
            width=width,
            height=height,
        )
    else:
        result.add_evidence(
            check="dimensions",
            passed=True,
            severity="info",
            message="Las dimensiones no son anormalmente pequeñas.",
            width=width,
            height=height,
        )

    entropy = calculate_entropy(image)

    result.add_evidence(
        check="entropy",
        passed=True,
        severity="info",
        message="Se calculó la entropía visual.",
        entropy=round(entropy, 4),
    )

    # Una entropía muy baja puede ser perfectamente válida:
    # logos, capturas vacías, fondos, documentos, máscaras, etc.
    if entropy < 0.15:
        result.add_evidence(
            check="very_low_entropy",
            passed=False,
            severity="review",
            message=(
                "La imagen presenta una entropía extremadamente baja. "
                "Puede ser válida, pero conviene revisarla."
            ),
            entropy=round(entropy, 4),
        )

    dominant_ratio = calculate_dominant_pixel_ratio(image)

    result.add_evidence(
        check="dominant_pixel_ratio",
        passed=True,
        severity="info",
        message="Se calculó la proporción del valor de píxel dominante.",
        ratio=round(dominant_ratio, 4),
    )

    if dominant_ratio > 0.995:
        result.add_evidence(
            check="excessive_dominant_pixel",
            passed=False,
            severity="review",
            message=(
                "Más del 99.5 % de la imagen tiene el mismo valor de píxel. "
                "Puede ser una imagen válida casi uniforme."
            ),
            ratio=round(dominant_ratio, 4),
        )

    uniform_block_ratio = calculate_uniform_block_ratio(image)

    result.add_evidence(
        check="uniform_blocks",
        passed=True,
        severity="info",
        message="Se analizaron regiones visualmente uniformes.",
        ratio=round(uniform_block_ratio, 4),
    )

    if uniform_block_ratio > 0.98 and entropy < 0.5:
        result.add_evidence(
            check="excessive_uniformity",
            passed=False,
            severity="review",
            message=(
                "Casi toda la imagen está formada por regiones uniformes. "
                "No se marca como rota automáticamente."
            ),
            uniform_block_ratio=round(uniform_block_ratio, 4),
            entropy=round(entropy, 4),
        )