from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image

from src.settings import (
    ANOMALOUS_PIXEL_DISTANCE,
    ANOMALOUS_PIXEL_MEDIAN_KERNEL,
    ANOMALOUS_PIXEL_RATIO,
    ARTIFACT_ANALYSIS_MAX_SIZE,
    ARTIFICIAL_BAND_MIN_FLAT_RATIO,
    ARTIFICIAL_BAND_MIN_TRANSITION,
    BAND_COUNT,
    BOTTOM_TRUNCATION_TEXTURE_DIFFERENCE,
    COLOR_CAST_MIN_SATURATION_RATIO,
    COLOR_CHANNEL_IMBALANCE_RATIO,
    EDGE_BAND_RATIO,
    EDGE_FLAT_VARIANCE,
    EDGE_TEXTURE_DIFFERENCE,
    EXTREME_NOISE_COLOR_JUMP_THRESHOLD,
    EXTREME_NOISE_MIN_BRIGHTNESS,
    EXTREME_NOISE_MIN_COLOR_JUMP_RATIO,
    EXTREME_NOISE_MIN_SATURATED_RATIO,
    EXTREME_NOISE_MIN_SATURATION,
    FLAT_TILE_VARIANCE,
    LARGE_FLAT_REGION_TILE_RATIO,
    LOW_INFORMATION_ENTROPY,
    LOW_INFORMATION_GRAY_STD,
    LOW_INFORMATION_UNIQUE_RATIO,
    PLACEHOLDER_EDGE_DENSITY,
    PLACEHOLDER_ENTROPY,
    PLACEHOLDER_UNIQUE_RATIO,
    SEVERE_ANOMALOUS_PIXEL_RATIO,
    TILE_GRID_SIZE,
)


@dataclass
class VisualIssue:
    code: str
    message: str
    level: str


@dataclass
class VisualAnalysisResult:
    broken_issues: list[VisualIssue] = field(default_factory=list)
    warning_issues: list[VisualIssue] = field(default_factory=list)
    info_issues: list[VisualIssue] = field(default_factory=list)
    metrics: dict[str, float | int | str | bool] = field(default_factory=dict)

    @property
    def all_issues(self) -> list[VisualIssue]:
        return self.broken_issues + self.warning_issues + self.info_issues


def analyze_visual_corruption(image: Image.Image) -> VisualAnalysisResult:
    image_array = pil_to_rgb_array(image)
    image_array = resize_for_analysis(image_array)

    result = VisualAnalysisResult()

    low_info_issues, low_info_metrics = detect_low_information(image_array)
    flat_region_issues, flat_region_metrics = detect_large_flat_regions(image_array)
    flat_edge_issues, flat_edge_metrics = detect_flat_edge_bands(image_array)
    bottom_issues, bottom_metrics = detect_possible_bottom_truncation(image_array)
    band_issues, band_metrics = detect_artificial_bands(image_array)
    pixel_issues, pixel_metrics = detect_anomalous_pixels(image_array)
    channel_issues, channel_metrics = detect_color_channel_imbalance(image_array)
    placeholder_issues, placeholder_metrics = detect_placeholder_like_image(image_array)
    extreme_noise_issues, extreme_noise_metrics = detect_extreme_rgb_noise(image_array)

    result.warning_issues.extend(low_info_issues)
    result.info_issues.extend(flat_region_issues)
    result.warning_issues.extend(flat_edge_issues)
    result.warning_issues.extend(bottom_issues)
    result.warning_issues.extend(band_issues)
    result.warning_issues.extend(pixel_issues)
    result.warning_issues.extend(channel_issues)
    result.warning_issues.extend(placeholder_issues)
    result.broken_issues.extend(extreme_noise_issues)

    result.metrics.update(low_info_metrics)
    result.metrics.update(flat_region_metrics)
    result.metrics.update(flat_edge_metrics)
    result.metrics.update(bottom_metrics)
    result.metrics.update(band_metrics)
    result.metrics.update(pixel_metrics)
    result.metrics.update(channel_metrics)
    result.metrics.update(placeholder_metrics)
    result.metrics.update(extreme_noise_metrics)

    return result


def pil_to_rgb_array(image: Image.Image) -> np.ndarray:
    return np.array(image.convert("RGB"))


def resize_for_analysis(image_array: np.ndarray) -> np.ndarray:
    height, width = image_array.shape[:2]
    max_side = max(width, height)

    if max_side <= ARTIFACT_ANALYSIS_MAX_SIZE:
        return image_array

    scale = ARTIFACT_ANALYSIS_MAX_SIZE / max_side
    new_width = max(1, int(width * scale))
    new_height = max(1, int(height * scale))

    return cv2.resize(image_array, (new_width, new_height), interpolation=cv2.INTER_AREA)


def detect_low_information(image_array: np.ndarray) -> tuple[list[VisualIssue], dict[str, float]]:
    gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)

    gray_std = float(np.std(gray))
    entropy = calculate_entropy(gray)
    unique_ratio = calculate_unique_color_ratio(image_array)
    edge_density = calculate_edge_density(gray)

    metrics = {
        "gray_std": round(gray_std, 4),
        "entropy": round(entropy, 4),
        "unique_color_ratio": round(unique_ratio, 6),
        "edge_density": round(edge_density, 6),
    }

    issues: list[VisualIssue] = []

    if (
        gray_std <= LOW_INFORMATION_GRAY_STD
        and entropy <= LOW_INFORMATION_ENTROPY
        and unique_ratio <= LOW_INFORMATION_UNIQUE_RATIO
    ):
        issues.append(
            VisualIssue(
                code="very_low_information",
                level="warning",
                message="Image has very low visual information.",
            )
        )

    return issues, metrics


def detect_placeholder_like_image(image_array: np.ndarray) -> tuple[list[VisualIssue], dict[str, float]]:
    gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)

    entropy = calculate_entropy(gray)
    unique_ratio = calculate_unique_color_ratio(image_array)
    edge_density = calculate_edge_density(gray)

    metrics = {
        "placeholder_entropy": round(entropy, 4),
        "placeholder_unique_color_ratio": round(unique_ratio, 6),
        "placeholder_edge_density": round(edge_density, 6),
    }

    issues: list[VisualIssue] = []

    if (
        entropy <= PLACEHOLDER_ENTROPY
        and unique_ratio <= PLACEHOLDER_UNIQUE_RATIO
        and edge_density <= PLACEHOLDER_EDGE_DENSITY
    ):
        issues.append(
            VisualIssue(
                code="possible_placeholder",
                level="warning",
                message="Image looks like a placeholder or very low-information image.",
            )
        )

    return issues, metrics


def detect_large_flat_regions(image_array: np.ndarray) -> tuple[list[VisualIssue], dict[str, float]]:
    gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
    height, width = gray.shape[:2]

    variances: list[float] = []

    for row in range(TILE_GRID_SIZE):
        for column in range(TILE_GRID_SIZE):
            top = int(row * height / TILE_GRID_SIZE)
            bottom = int((row + 1) * height / TILE_GRID_SIZE)
            left = int(column * width / TILE_GRID_SIZE)
            right = int((column + 1) * width / TILE_GRID_SIZE)

            tile = gray[top:bottom, left:right]

            if tile.size > 0:
                variances.append(float(np.var(tile)))

    flat_tiles = [variance for variance in variances if variance <= FLAT_TILE_VARIANCE]
    flat_ratio = len(flat_tiles) / len(variances) if variances else 0.0

    metrics = {
        "flat_tile_ratio": round(flat_ratio, 6),
        "tile_variance_mean": round(float(np.mean(variances)) if variances else 0.0, 4),
        "tile_variance_median": round(float(np.median(variances)) if variances else 0.0, 4),
    }

    issues: list[VisualIssue] = []

    if flat_ratio >= LARGE_FLAT_REGION_TILE_RATIO:
        issues.append(
            VisualIssue(
                code="large_flat_regions",
                level="info",
                message=(
                    "Image contains large flat regions. This can be valid "
                    "and is not a rejection reason by itself."
                ),
            )
        )

    return issues, metrics


def detect_flat_edge_bands(image_array: np.ndarray) -> tuple[list[VisualIssue], dict[str, float | int | str]]:
    height, width = image_array.shape[:2]

    band_height = max(1, int(height * EDGE_BAND_RATIO))
    band_width = max(1, int(width * EDGE_BAND_RATIO))

    candidates = {
        "top": (
            image_array[:band_height, :],
            image_array[band_height : min(height, band_height * 2), :],
        ),
        "bottom": (
            image_array[height - band_height :, :],
            image_array[max(0, height - band_height * 2) : height - band_height, :],
        ),
        "left": (
            image_array[:, :band_width],
            image_array[:, band_width : min(width, band_width * 2)],
        ),
        "right": (
            image_array[:, width - band_width :],
            image_array[:, max(0, width - band_width * 2) : width - band_width],
        ),
    }

    metrics: dict[str, float | int | str] = {}
    suspicious_edges: list[str] = []

    for edge_name, (edge_region, context_region) in candidates.items():
        if edge_region.size == 0 or context_region.size == 0:
            continue

        edge_variance = calculate_gray_variance(edge_region)
        context_variance = calculate_gray_variance(context_region)
        texture_difference = max(0.0, context_variance - edge_variance)

        metrics[f"{edge_name}_edge_variance"] = round(edge_variance, 4)
        metrics[f"{edge_name}_context_variance"] = round(context_variance, 4)
        metrics[f"{edge_name}_texture_difference"] = round(texture_difference, 4)

        if edge_variance <= EDGE_FLAT_VARIANCE and texture_difference >= EDGE_TEXTURE_DIFFERENCE:
            suspicious_edges.append(edge_name)

    metrics["flat_edge_count"] = len(suspicious_edges)
    metrics["flat_edges"] = ", ".join(suspicious_edges)

    issues: list[VisualIssue] = []

    if suspicious_edges:
        issues.append(
            VisualIssue(
                code="flat_edge_band",
                level="warning",
                message=(
                    f"Flat edge band detected on: {', '.join(suspicious_edges)}. "
                    "This is only a soft signal."
                ),
            )
        )

    return issues, metrics


def detect_possible_bottom_truncation(image_array: np.ndarray) -> tuple[list[VisualIssue], dict[str, float]]:
    height, _ = image_array.shape[:2]
    band_height = max(1, int(height * EDGE_BAND_RATIO))

    bottom = image_array[height - band_height :, :]
    upper_context = image_array[max(0, height - band_height * 3) : height - band_height, :]

    metrics: dict[str, float] = {}
    issues: list[VisualIssue] = []

    if bottom.size == 0 or upper_context.size == 0:
        return issues, metrics

    bottom_variance = calculate_gray_variance(bottom)
    context_variance = calculate_gray_variance(upper_context)
    texture_difference = context_variance - bottom_variance

    metrics["bottom_band_variance"] = round(bottom_variance, 4)
    metrics["bottom_context_variance"] = round(context_variance, 4)
    metrics["bottom_texture_difference"] = round(texture_difference, 4)

    if bottom_variance <= EDGE_FLAT_VARIANCE and texture_difference >= BOTTOM_TRUNCATION_TEXTURE_DIFFERENCE:
        issues.append(
            VisualIssue(
                code="possible_bottom_truncation",
                level="warning",
                message="Bottom edge looks unusually flat compared with the rest of the image.",
            )
        )

    return issues, metrics


def detect_artificial_bands(image_array: np.ndarray) -> tuple[list[VisualIssue], dict[str, float | int]]:
    horizontal_issues, horizontal_metrics = detect_artificial_bands_by_axis(image_array, axis="horizontal")
    vertical_issues, vertical_metrics = detect_artificial_bands_by_axis(image_array, axis="vertical")

    return horizontal_issues + vertical_issues, {**horizontal_metrics, **vertical_metrics}


def detect_artificial_bands_by_axis(
    image_array: np.ndarray,
    axis: str,
) -> tuple[list[VisualIssue], dict[str, float | int]]:
    gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
    height, width = gray.shape[:2]

    band_variances: list[float] = []
    band_means: list[float] = []

    for index in range(BAND_COUNT):
        if axis == "horizontal":
            start = int(index * height / BAND_COUNT)
            end = int((index + 1) * height / BAND_COUNT)
            band = gray[start:end, :]
        else:
            start = int(index * width / BAND_COUNT)
            end = int((index + 1) * width / BAND_COUNT)
            band = gray[:, start:end]

        if band.size > 0:
            band_variances.append(float(np.var(band)))
            band_means.append(float(np.mean(band)))

    metrics: dict[str, float | int] = {}

    if not band_variances:
        return [], metrics

    flat_bands = [variance for variance in band_variances if variance <= EDGE_FLAT_VARIANCE]
    flat_ratio = len(flat_bands) / len(band_variances)

    abrupt_transitions = 0

    for index in range(1, len(band_means)):
        if abs(band_means[index] - band_means[index - 1]) >= ARTIFICIAL_BAND_MIN_TRANSITION:
            abrupt_transitions += 1

    metrics[f"{axis}_flat_band_ratio"] = round(flat_ratio, 6)
    metrics[f"{axis}_abrupt_band_transitions"] = abrupt_transitions

    issues: list[VisualIssue] = []

    if flat_ratio >= ARTIFICIAL_BAND_MIN_FLAT_RATIO and abrupt_transitions >= 2:
        issue_code = "artificial_horizontal_bands" if axis == "horizontal" else "artificial_vertical_bands"
        issues.append(
            VisualIssue(
                code=issue_code,
                level="warning",
                message=f"Possible artificial {axis} bands detected. This is only a soft signal.",
            )
        )

    return issues, metrics


def detect_anomalous_pixels(image_array: np.ndarray) -> tuple[list[VisualIssue], dict[str, float]]:
    kernel = ANOMALOUS_PIXEL_MEDIAN_KERNEL

    if kernel % 2 == 0:
        kernel += 1

    median = cv2.medianBlur(image_array, kernel)
    difference = np.linalg.norm(
        image_array.astype(np.float32) - median.astype(np.float32),
        axis=2,
    )

    anomalous_ratio = float(np.mean(difference >= ANOMALOUS_PIXEL_DISTANCE))

    metrics = {
        "anomalous_pixel_ratio": round(anomalous_ratio, 6),
    }

    issues: list[VisualIssue] = []

    if anomalous_ratio >= SEVERE_ANOMALOUS_PIXEL_RATIO:
        issues.append(
            VisualIssue(
                code="severe_anomalous_pixels",
                level="warning",
                message=f"Severe anomalous pixel ratio detected: {anomalous_ratio:.2%}.",
            )
        )
    elif anomalous_ratio >= ANOMALOUS_PIXEL_RATIO:
        issues.append(
            VisualIssue(
                code="anomalous_pixels",
                level="warning",
                message=f"Anomalous pixel ratio detected: {anomalous_ratio:.2%}.",
            )
        )

    return issues, metrics


def detect_extreme_rgb_noise(image_array: np.ndarray) -> tuple[list[VisualIssue], dict[str, float]]:
    saturated_ratio = calculate_saturated_ratio(
        image_array,
        min_saturation=EXTREME_NOISE_MIN_SATURATION,
        min_brightness=EXTREME_NOISE_MIN_BRIGHTNESS,
    )
    color_jump_ratio = calculate_color_jump_ratio(
        image_array,
        threshold=EXTREME_NOISE_COLOR_JUMP_THRESHOLD,
    )

    metrics = {
        "extreme_noise_saturated_ratio": round(saturated_ratio, 6),
        "extreme_noise_color_jump_ratio": round(color_jump_ratio, 6),
    }

    issues: list[VisualIssue] = []

    if (
        saturated_ratio >= EXTREME_NOISE_MIN_SATURATED_RATIO
        and color_jump_ratio >= EXTREME_NOISE_MIN_COLOR_JUMP_RATIO
    ):
        issues.append(
            VisualIssue(
                code="extreme_rgb_noise",
                level="broken",
                message=(
                    "Extreme global RGB noise detected "
                    f"(saturation {saturated_ratio:.0%}, color jumps {color_jump_ratio:.0%})."
                ),
            )
        )

    return issues, metrics


def detect_color_channel_imbalance(image_array: np.ndarray) -> tuple[list[VisualIssue], dict[str, float]]:
    flat = image_array.reshape(-1, 3)

    channel_means = np.mean(flat, axis=0)
    channel_stds = np.std(flat, axis=0)

    min_mean = float(np.min(channel_means))
    max_mean = float(np.max(channel_means))
    mean_ratio = max_mean / max(min_mean, 1.0)
    saturation_ratio = calculate_saturated_ratio(image_array, min_saturation=100, min_brightness=35)

    metrics = {
        "red_mean": round(float(channel_means[0]), 4),
        "green_mean": round(float(channel_means[1]), 4),
        "blue_mean": round(float(channel_means[2]), 4),
        "red_std": round(float(channel_stds[0]), 4),
        "green_std": round(float(channel_stds[1]), 4),
        "blue_std": round(float(channel_stds[2]), 4),
        "channel_mean_ratio": round(mean_ratio, 4),
        "saturation_ratio": round(saturation_ratio, 6),
    }

    issues: list[VisualIssue] = []

    if mean_ratio >= COLOR_CHANNEL_IMBALANCE_RATIO and saturation_ratio >= COLOR_CAST_MIN_SATURATION_RATIO:
        issues.append(
            VisualIssue(
                code="color_channel_imbalance",
                level="warning",
                message="Possible broken or heavily imbalanced color channel detected.",
            )
        )

    return issues, metrics


def calculate_color_jump_ratio(image_array: np.ndarray, threshold: int) -> float:
    if image_array.shape[0] < 2 or image_array.shape[1] < 2:
        return 0.0

    image_float = image_array.astype(np.float32)

    horizontal_diff = np.linalg.norm(image_float[:, 1:, :] - image_float[:, :-1, :], axis=2)
    vertical_diff = np.linalg.norm(image_float[1:, :, :] - image_float[:-1, :, :], axis=2)

    horizontal_jumps = np.mean(horizontal_diff >= threshold)
    vertical_jumps = np.mean(vertical_diff >= threshold)

    return float((horizontal_jumps + vertical_jumps) / 2)


def calculate_saturated_ratio(
    image_array: np.ndarray,
    min_saturation: int,
    min_brightness: int,
) -> float:
    hsv = cv2.cvtColor(image_array, cv2.COLOR_RGB2HSV)
    saturation = hsv[:, :, 1]
    brightness = hsv[:, :, 2]

    return float(np.mean((saturation >= min_saturation) & (brightness >= min_brightness)))


def calculate_entropy(gray_image: np.ndarray) -> float:
    histogram = cv2.calcHist([gray_image], [0], None, [256], [0, 256])
    probabilities = histogram.ravel() / max(float(np.sum(histogram)), 1.0)
    probabilities = probabilities[probabilities > 0]

    return float(-np.sum(probabilities * np.log2(probabilities)))


def calculate_unique_color_ratio(image_array: np.ndarray) -> float:
    small = cv2.resize(image_array, (96, 96), interpolation=cv2.INTER_AREA)
    quantized = (small // 16).astype(np.uint8)
    flat = quantized.reshape(-1, 3)
    unique_colors = np.unique(flat, axis=0)

    return float(len(unique_colors) / len(flat))


def calculate_edge_density(gray_image: np.ndarray) -> float:
    edges = cv2.Canny(gray_image, 80, 160)
    return float(np.mean(edges > 0))


def calculate_gray_variance(image_array: np.ndarray) -> float:
    gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
    return float(np.var(gray))