from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image

from src.settings import (
    ARTIFACT_ANALYSIS_MAX_SIZE,
    DAMAGED_BLOCK_GRID_SIZE,
    DAMAGED_BLOCK_MIN_COLOR_JUMP_RATIO,
    DAMAGED_BLOCK_MIN_RATIO,
    DAMAGED_BLOCK_MIN_SATURATED_RATIO,
    DAMAGED_BLOCKS_SCORE,
    EXTREME_NOISE_COLOR_JUMP_THRESHOLD,
    EXTREME_NOISE_MIN_BRIGHTNESS,
    EXTREME_NOISE_MIN_COLOR_JUMP_RATIO,
    EXTREME_NOISE_MIN_SATURATED_RATIO,
    EXTREME_NOISE_MIN_SATURATION,
    EXTREME_NOISE_SCORE,
    GLOBAL_SEAM_EDGE_IGNORE_RATIO,
    GLOBAL_SEAM_MIN_DIFFERENCE,
    GLOBAL_SEAM_OUTLIER_MULTIPLIER,
    GLOBAL_SEAM_SCORE,
    PANEL_DAMAGE_SCORE,
    PANEL_MIN_CONTEXT_DIFFERENCE,
    PANEL_MIN_SATURATED_RATIO,
    PANEL_MIN_SEAM_DIFFERENCE,
    PANEL_SCAN_RATIO,
    SOLID_EDGE_MAX_GRAY_VARIANCE,
    SOLID_EDGE_MIN_CONTEXT_DIFFERENCE,
    SOLID_EDGE_MIN_DOMINANT_RATIO,
    SOLID_EDGE_REPLACEMENT_SCORE,
    SOLID_EDGE_RATIO,
    UNUSABLE_SCORE_THRESHOLD,
)


@dataclass
class CorruptionDetectionResult:
    score: float = 0.0
    critical_reasons: list[str] = field(default_factory=list)
    warning_reasons: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class DetectionSignal:
    score: float
    reason: str


def detect_visual_corruption(image: Image.Image) -> CorruptionDetectionResult:
    cv_image = pil_to_cv_rgb(image)
    cv_image = resize_for_analysis(cv_image)

    signals: list[DetectionSignal] = []
    signals.extend(detect_extreme_rgb_noise(cv_image))
    signals.extend(detect_solid_edge_replacement(cv_image))
    signals.extend(detect_large_panel_damage(cv_image))
    signals.extend(detect_global_seams(cv_image))
    signals.extend(detect_damaged_block_mosaic(cv_image))

    total_score = sum(signal.score for signal in signals)
    reasons = [signal.reason for signal in signals]

    result = CorruptionDetectionResult(score=total_score)

    if total_score >= UNUSABLE_SCORE_THRESHOLD:
        result.critical_reasons = remove_duplicate_strings(reasons)
    else:
        result.warning_reasons = remove_duplicate_strings(reasons)

    result.metrics["visual_corruption_score"] = total_score

    return result


def pil_to_cv_rgb(image: Image.Image) -> np.ndarray:
    rgb_image = image.convert("RGB")
    return np.array(rgb_image)


def resize_for_analysis(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    max_side = max(width, height)

    if max_side <= ARTIFACT_ANALYSIS_MAX_SIZE:
        return image

    scale = ARTIFACT_ANALYSIS_MAX_SIZE / max_side
    new_width = max(1, int(width * scale))
    new_height = max(1, int(height * scale))

    return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)


def detect_extreme_rgb_noise(image: np.ndarray) -> list[DetectionSignal]:
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)

    saturation = hsv[:, :, 1]
    brightness = hsv[:, :, 2]

    saturated_mask = (
        (saturation >= EXTREME_NOISE_MIN_SATURATION)
        & (brightness >= EXTREME_NOISE_MIN_BRIGHTNESS)
    )

    saturated_ratio = float(np.mean(saturated_mask))
    color_jump_ratio = calculate_color_jump_ratio(
        image,
        threshold=EXTREME_NOISE_COLOR_JUMP_THRESHOLD,
    )

    if (
        saturated_ratio >= EXTREME_NOISE_MIN_SATURATED_RATIO
        and color_jump_ratio >= EXTREME_NOISE_MIN_COLOR_JUMP_RATIO
    ):
        return [
            DetectionSignal(
                score=EXTREME_NOISE_SCORE,
                reason=(
                    "Unusable image: extreme RGB noise detected "
                    f"(saturation {saturated_ratio:.0%}, color jumps {color_jump_ratio:.0%})"
                ),
            )
        ]

    return []


def detect_solid_edge_replacement(image: np.ndarray) -> list[DetectionSignal]:
    height, width = image.shape[:2]

    if width < 20 or height < 20:
        return []

    band_height = max(1, int(height * SOLID_EDGE_RATIO))
    band_width = max(1, int(width * SOLID_EDGE_RATIO))

    candidates = [
        (
            "top",
            image[0:band_height, :],
            image[band_height : min(height, band_height * 2), :],
        ),
        (
            "bottom",
            image[height - band_height : height, :],
            image[max(0, height - band_height * 2) : height - band_height, :],
        ),
        (
            "left",
            image[:, 0:band_width],
            image[:, band_width : min(width, band_width * 2)],
        ),
        (
            "right",
            image[:, width - band_width : width],
            image[:, max(0, width - band_width * 2) : width - band_width],
        ),
    ]

    signals: list[DetectionSignal] = []

    for label, region, context in candidates:
        if region.size == 0 or context.size == 0:
            continue

        dominant_ratio = calculate_dominant_color_ratio(region)
        gray_variance = calculate_gray_variance(region)
        context_difference = calculate_mean_color_difference(region, context)

        is_solid_replacement = (
            dominant_ratio >= SOLID_EDGE_MIN_DOMINANT_RATIO
            and gray_variance <= SOLID_EDGE_MAX_GRAY_VARIANCE
            and context_difference >= SOLID_EDGE_MIN_CONTEXT_DIFFERENCE
        )

        if is_solid_replacement:
            signals.append(
                DetectionSignal(
                    score=SOLID_EDGE_REPLACEMENT_SCORE,
                    reason=(
                        "Unusable image: large solid edge replacement detected "
                        f"on {label} edge"
                    ),
                )
            )

    return signals


def detect_large_panel_damage(image: np.ndarray) -> list[DetectionSignal]:
    height, width = image.shape[:2]

    if width < 30 or height < 30:
        return []

    panel_width = max(1, int(width * PANEL_SCAN_RATIO))
    panel_height = max(1, int(height * PANEL_SCAN_RATIO))

    center = crop_center(image, 0.35, 0.65, 0.35, 0.65)

    candidates = [
        (
            "left",
            image[:, 0:panel_width],
            image[:, panel_width : min(width, panel_width * 2)],
        ),
        (
            "right",
            image[:, width - panel_width : width],
            image[:, max(0, width - panel_width * 2) : width - panel_width],
        ),
        (
            "top",
            image[0:panel_height, :],
            image[panel_height : min(height, panel_height * 2), :],
        ),
        (
            "bottom",
            image[height - panel_height : height, :],
            image[max(0, height - panel_height * 2) : height - panel_height, :],
        ),
    ]

    signals: list[DetectionSignal] = []

    for label, panel, adjacent in candidates:
        if panel.size == 0 or adjacent.size == 0 or center.size == 0:
            continue

        context_difference = calculate_mean_color_difference(panel, center)
        seam_difference = calculate_mean_color_difference(panel, adjacent)
        saturated_ratio = calculate_saturated_ratio(panel)

        is_panel_damage = (
            context_difference >= PANEL_MIN_CONTEXT_DIFFERENCE
            and seam_difference >= PANEL_MIN_SEAM_DIFFERENCE
            and saturated_ratio >= PANEL_MIN_SATURATED_RATIO
        )

        if is_panel_damage:
            signals.append(
                DetectionSignal(
                    score=PANEL_DAMAGE_SCORE,
                    reason=(
                        "Possible unusable image: large damaged panel detected "
                        f"on {label} side"
                    ),
                )
            )

    return signals


def detect_global_seams(image: np.ndarray) -> list[DetectionSignal]:
    signals: list[DetectionSignal] = []

    vertical_seam = detect_axis_seam(image, axis="vertical")
    horizontal_seam = detect_axis_seam(image, axis="horizontal")

    if vertical_seam is not None:
        position_ratio, seam_score, baseline = vertical_seam
        signals.append(
            DetectionSignal(
                score=GLOBAL_SEAM_SCORE,
                reason=(
                    "Possible unusable image: strong vertical split detected "
                    f"at {position_ratio:.0%} of width "
                    f"(score {seam_score:.1f}, baseline {baseline:.1f})"
                ),
            )
        )

    if horizontal_seam is not None:
        position_ratio, seam_score, baseline = horizontal_seam
        signals.append(
            DetectionSignal(
                score=GLOBAL_SEAM_SCORE,
                reason=(
                    "Possible unusable image: strong horizontal split detected "
                    f"at {position_ratio:.0%} of height "
                    f"(score {seam_score:.1f}, baseline {baseline:.1f})"
                ),
            )
        )

    return signals


def detect_axis_seam(
    image: np.ndarray,
    axis: str,
) -> tuple[float, float, float] | None:
    height, width = image.shape[:2]

    if width < 20 or height < 20:
        return None

    if axis == "vertical":
        diffs = np.mean(
            np.linalg.norm(
                image[:, 1:, :].astype(np.float32) - image[:, :-1, :].astype(np.float32),
                axis=2,
            ),
            axis=0,
        )
        length = width
    else:
        diffs = np.mean(
            np.linalg.norm(
                image[1:, :, :].astype(np.float32) - image[:-1, :, :].astype(np.float32),
                axis=2,
            ),
            axis=1,
        )
        length = height

    if len(diffs) < 10:
        return None

    edge_ignore = max(1, int(len(diffs) * GLOBAL_SEAM_EDGE_IGNORE_RATIO))
    usable_diffs = diffs[edge_ignore : len(diffs) - edge_ignore]

    if len(usable_diffs) == 0:
        return None

    max_index_local = int(np.argmax(usable_diffs))
    max_score = float(usable_diffs[max_index_local])
    max_index = max_index_local + edge_ignore
    baseline = float(np.percentile(usable_diffs, 95))

    if baseline <= 0:
        return None

    is_outlier = max_score >= baseline * GLOBAL_SEAM_OUTLIER_MULTIPLIER
    is_strong = max_score >= GLOBAL_SEAM_MIN_DIFFERENCE

    if is_outlier and is_strong:
        return max_index / length, max_score, baseline

    return None


def detect_damaged_block_mosaic(image: np.ndarray) -> list[DetectionSignal]:
    blocks = split_into_grid(image, DAMAGED_BLOCK_GRID_SIZE)

    if not blocks:
        return []

    damaged_blocks = 0

    for block in blocks:
        saturated_ratio = calculate_saturated_ratio(block)
        color_jump_ratio = calculate_color_jump_ratio(
            block,
            threshold=EXTREME_NOISE_COLOR_JUMP_THRESHOLD,
        )

        if (
            saturated_ratio >= DAMAGED_BLOCK_MIN_SATURATED_RATIO
            and color_jump_ratio >= DAMAGED_BLOCK_MIN_COLOR_JUMP_RATIO
        ):
            damaged_blocks += 1

    damaged_ratio = damaged_blocks / len(blocks)

    if damaged_ratio >= DAMAGED_BLOCK_MIN_RATIO:
        return [
            DetectionSignal(
                score=DAMAGED_BLOCKS_SCORE,
                reason=(
                    "Possible unusable image: damaged RGB block mosaic detected "
                    f"({damaged_ratio:.0%} damaged blocks)"
                ),
            )
        ]

    return []


def calculate_color_jump_ratio(image: np.ndarray, threshold: int) -> float:
    if image.shape[0] < 2 or image.shape[1] < 2:
        return 0.0

    image_float = image.astype(np.float32)

    horizontal_diff = np.linalg.norm(image_float[:, 1:, :] - image_float[:, :-1, :], axis=2)
    vertical_diff = np.linalg.norm(image_float[1:, :, :] - image_float[:-1, :, :], axis=2)

    horizontal_jumps = np.mean(horizontal_diff >= threshold)
    vertical_jumps = np.mean(vertical_diff >= threshold)

    return float((horizontal_jumps + vertical_jumps) / 2)


def calculate_saturated_ratio(image: np.ndarray) -> float:
    if image.size == 0:
        return 0.0

    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    saturation = hsv[:, :, 1]
    brightness = hsv[:, :, 2]

    mask = (saturation >= EXTREME_NOISE_MIN_SATURATION) & (
        brightness >= EXTREME_NOISE_MIN_BRIGHTNESS
    )

    return float(np.mean(mask))


def calculate_dominant_color_ratio(image: np.ndarray) -> float:
    if image.size == 0:
        return 0.0

    small = cv2.resize(image, (80, 80), interpolation=cv2.INTER_AREA)
    quantized = (small // 24).astype(np.uint8)
    flat = quantized.reshape(-1, 3)

    _, counts = np.unique(flat, axis=0, return_counts=True)

    return float(np.max(counts) / np.sum(counts))


def calculate_gray_variance(image: np.ndarray) -> float:
    if image.size == 0:
        return 0.0

    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    return float(np.var(gray))


def calculate_mean_color_difference(first: np.ndarray, second: np.ndarray) -> float:
    if first.size == 0 or second.size == 0:
        return 0.0

    first_mean = np.mean(first.reshape(-1, 3), axis=0)
    second_mean = np.mean(second.reshape(-1, 3), axis=0)

    return float(np.linalg.norm(first_mean - second_mean))


def crop_center(
    image: np.ndarray,
    left_ratio: float,
    right_ratio: float,
    top_ratio: float,
    bottom_ratio: float,
) -> np.ndarray:
    height, width = image.shape[:2]

    left = int(width * left_ratio)
    right = int(width * right_ratio)
    top = int(height * top_ratio)
    bottom = int(height * bottom_ratio)

    return image[top:bottom, left:right]


def split_into_grid(image: np.ndarray, grid_size: int) -> list[np.ndarray]:
    height, width = image.shape[:2]

    if width < grid_size or height < grid_size:
        return []

    blocks: list[np.ndarray] = []

    for row in range(grid_size):
        for column in range(grid_size):
            top = int(row * height / grid_size)
            bottom = int((row + 1) * height / grid_size)
            left = int(column * width / grid_size)
            right = int((column + 1) * width / grid_size)

            block = image[top:bottom, left:right]

            if block.size > 0:
                blocks.append(block)

    return blocks


def remove_duplicate_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        if value in seen:
            continue

        seen.add(value)
        result.append(value)

    return result