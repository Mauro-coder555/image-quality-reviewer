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
    GLITCH_BLOCK_GRID_SIZE,
    GLITCH_BLOCK_MIN_BAD_RATIO,
    GLITCH_BLOCK_MIN_COLOR_JUMP_RATIO,
    GLITCH_BLOCK_MIN_SATURATED_RATIO,
    LARGE_FLAT_REGION_TILE_RATIO,
    LOW_INFORMATION_ENTROPY,
    LOW_INFORMATION_GRAY_STD,
    LOW_INFORMATION_UNIQUE_RATIO,
    PLACEHOLDER_EDGE_DENSITY,
    PLACEHOLDER_ENTROPY,
    PLACEHOLDER_UNIQUE_RATIO,
    REPLACEMENT_REGION_MAX_VARIANCE,
    REPLACEMENT_REGION_MIN_AREA_RATIO,
    REPLACEMENT_REGION_MIN_CONTEXT_DIFFERENCE,
    REPLACEMENT_REGION_MIN_CONTEXT_VARIANCE,
    REPLACEMENT_REGION_MIN_DOMINANT_RATIO,
    REPLACEMENT_REGION_MIN_SEAM_DIFFERENCE,
    SEVERE_ANOMALOUS_PIXEL_RATIO,
    TILE_GRID_SIZE,
    TINTED_PANEL_MIN_AREA_RATIO,
    TINTED_PANEL_MIN_COLOR_DISTANCE,
    TINTED_PANEL_MIN_SATURATION,
    TINTED_PANEL_MIN_SEAM_DIFFERENCE,
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

    replacement_issues, replacement_metrics = detect_large_artificial_replacement_regions(image_array)
    tinted_panel_issues, tinted_panel_metrics = detect_large_tinted_panel_corruption(image_array)
    glitch_block_issues, glitch_block_metrics = detect_glitch_block_corruption(image_array)
    decode_cut_issues, decode_cut_metrics = detect_strong_decode_cuts(image_array)

    result.warning_issues.extend(low_info_issues)
    result.info_issues.extend(flat_region_issues)
    result.warning_issues.extend(flat_edge_issues)
    result.warning_issues.extend(bottom_issues)
    result.warning_issues.extend(band_issues)
    result.warning_issues.extend(pixel_issues)
    result.warning_issues.extend(channel_issues)
    result.warning_issues.extend(placeholder_issues)

    # These are still "warning" issues, but their weights are high enough
    # to become Suspect in image_analysis.py. This avoids automatic deletion.
    result.warning_issues.extend(replacement_issues)
    result.warning_issues.extend(tinted_panel_issues)
    result.warning_issues.extend(glitch_block_issues)
    result.warning_issues.extend(decode_cut_issues)

    # Only extreme global noise becomes Broken directly.
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
    result.metrics.update(replacement_metrics)
    result.metrics.update(tinted_panel_metrics)
    result.metrics.update(glitch_block_metrics)
    result.metrics.update(decode_cut_metrics)

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


def detect_large_artificial_replacement_regions(
    image_array: np.ndarray,
) -> tuple[list[VisualIssue], dict[str, float | int | str]]:
    height, width = image_array.shape[:2]

    candidates = build_large_region_candidates(image_array)
    metrics: dict[str, float | int | str] = {}
    issues: list[VisualIssue] = []
    suspicious_regions: list[str] = []

    for label, region, context, seam_region in candidates:
        if region.size == 0 or context.size == 0 or seam_region.size == 0:
            continue

        area_ratio = calculate_area_ratio(region, width, height)
        gray_variance = calculate_gray_variance(region)
        context_variance = calculate_gray_variance(context)
        dominant_ratio = calculate_dominant_color_ratio(region)
        context_difference = calculate_mean_color_difference(region, context)
        seam_difference = calculate_mean_color_difference(region, seam_region)

        metrics[f"{label}_replacement_area_ratio"] = round(area_ratio, 6)
        metrics[f"{label}_replacement_gray_variance"] = round(gray_variance, 4)
        metrics[f"{label}_replacement_context_variance"] = round(context_variance, 4)
        metrics[f"{label}_replacement_dominant_ratio"] = round(dominant_ratio, 6)
        metrics[f"{label}_replacement_context_difference"] = round(context_difference, 4)
        metrics[f"{label}_replacement_seam_difference"] = round(seam_difference, 4)

        looks_like_replacement = (
            area_ratio >= REPLACEMENT_REGION_MIN_AREA_RATIO
            and gray_variance <= REPLACEMENT_REGION_MAX_VARIANCE
            and dominant_ratio >= REPLACEMENT_REGION_MIN_DOMINANT_RATIO
            and context_variance >= REPLACEMENT_REGION_MIN_CONTEXT_VARIANCE
            and context_difference >= REPLACEMENT_REGION_MIN_CONTEXT_DIFFERENCE
            and seam_difference >= REPLACEMENT_REGION_MIN_SEAM_DIFFERENCE
        )

        if looks_like_replacement:
            suspicious_regions.append(label)

    metrics["artificial_replacement_regions"] = ", ".join(suspicious_regions)
    metrics["artificial_replacement_region_count"] = len(suspicious_regions)

    if suspicious_regions:
        issues.append(
            VisualIssue(
                code="large_artificial_replacement_region",
                level="warning",
                message=(
                    "Large artificial replacement region detected: "
                    f"{', '.join(suspicious_regions)}."
                ),
            )
        )

    return issues, metrics


def detect_large_tinted_panel_corruption(
    image_array: np.ndarray,
) -> tuple[list[VisualIssue], dict[str, float | int | str]]:
    height, width = image_array.shape[:2]

    candidates = build_large_region_candidates(image_array)
    metrics: dict[str, float | int | str] = {}
    issues: list[VisualIssue] = []
    suspicious_panels: list[str] = []

    for label, region, context, seam_region in candidates:
        if region.size == 0 or context.size == 0 or seam_region.size == 0:
            continue

        area_ratio = calculate_area_ratio(region, width, height)
        color_difference = calculate_mean_color_difference(region, context)
        seam_difference = calculate_mean_color_difference(region, seam_region)
        saturation_ratio = calculate_saturated_ratio(region, min_saturation=90, min_brightness=35)

        metrics[f"{label}_tinted_area_ratio"] = round(area_ratio, 6)
        metrics[f"{label}_tinted_color_difference"] = round(color_difference, 4)
        metrics[f"{label}_tinted_seam_difference"] = round(seam_difference, 4)
        metrics[f"{label}_tinted_saturation_ratio"] = round(saturation_ratio, 6)

        looks_like_tinted_corruption = (
            area_ratio >= TINTED_PANEL_MIN_AREA_RATIO
            and color_difference >= TINTED_PANEL_MIN_COLOR_DISTANCE
            and seam_difference >= TINTED_PANEL_MIN_SEAM_DIFFERENCE
            and saturation_ratio >= TINTED_PANEL_MIN_SATURATION
        )

        if looks_like_tinted_corruption:
            suspicious_panels.append(label)

    metrics["tinted_panel_regions"] = ", ".join(suspicious_panels)
    metrics["tinted_panel_region_count"] = len(suspicious_panels)

    if suspicious_panels:
        issues.append(
            VisualIssue(
                code="large_tinted_panel_corruption",
                level="warning",
                message=(
                    "Large tinted panel corruption detected: "
                    f"{', '.join(suspicious_panels)}."
                ),
            )
        )

    return issues, metrics


def detect_glitch_block_corruption(
    image_array: np.ndarray,
) -> tuple[list[VisualIssue], dict[str, float | int]]:
    blocks = split_into_grid(image_array, GLITCH_BLOCK_GRID_SIZE)

    metrics: dict[str, float | int] = {}
    issues: list[VisualIssue] = []

    if not blocks:
        return issues, metrics

    bad_blocks = 0

    for block in blocks:
        saturated_ratio = calculate_saturated_ratio(
            block,
            min_saturation=EXTREME_NOISE_MIN_SATURATION,
            min_brightness=EXTREME_NOISE_MIN_BRIGHTNESS,
        )
        color_jump_ratio = calculate_color_jump_ratio(
            block,
            threshold=EXTREME_NOISE_COLOR_JUMP_THRESHOLD,
        )

        if (
            saturated_ratio >= GLITCH_BLOCK_MIN_SATURATED_RATIO
            and color_jump_ratio >= GLITCH_BLOCK_MIN_COLOR_JUMP_RATIO
        ):
            bad_blocks += 1

    bad_ratio = bad_blocks / len(blocks)

    metrics["glitch_bad_block_count"] = bad_blocks
    metrics["glitch_bad_block_ratio"] = round(bad_ratio, 6)

    if bad_ratio >= GLITCH_BLOCK_MIN_BAD_RATIO:
        issues.append(
            VisualIssue(
                code="glitch_block_corruption",
                level="warning",
                message=f"Glitch-like RGB block corruption detected ({bad_ratio:.0%} bad blocks).",
            )
        )

    return issues, metrics


def detect_strong_decode_cuts(
    image_array: np.ndarray,
) -> tuple[list[VisualIssue], dict[str, float | int | str]]:
    metrics: dict[str, float | int | str] = {}
    issues: list[VisualIssue] = []

    horizontal_cut = detect_decode_cut_by_axis(image_array, axis="horizontal")
    vertical_cut = detect_decode_cut_by_axis(image_array, axis="vertical")

    if horizontal_cut is not None:
        position, score, baseline = horizontal_cut
        metrics["strong_horizontal_cut_position"] = round(position, 6)
        metrics["strong_horizontal_cut_score"] = round(score, 4)
        metrics["strong_horizontal_cut_baseline"] = round(baseline, 4)

        issues.append(
            VisualIssue(
                code="strong_horizontal_decode_cut",
                level="warning",
                message=(
                    "Strong horizontal decode cut detected "
                    f"at {position:.0%} of image height."
                ),
            )
        )

    if vertical_cut is not None:
        position, score, baseline = vertical_cut
        metrics["strong_vertical_cut_position"] = round(position, 6)
        metrics["strong_vertical_cut_score"] = round(score, 4)
        metrics["strong_vertical_cut_baseline"] = round(baseline, 4)

        issues.append(
            VisualIssue(
                code="strong_vertical_decode_cut",
                level="warning",
                message=(
                    "Strong vertical decode cut detected "
                    f"at {position:.0%} of image width."
                ),
            )
        )

    return issues, metrics


def detect_decode_cut_by_axis(
    image_array: np.ndarray,
    axis: str,
) -> tuple[float, float, float] | None:
    image_float = image_array.astype(np.float32)

    height, width = image_array.shape[:2]

    if height < 40 or width < 40:
        return None

    if axis == "horizontal":
        diffs = np.mean(
            np.linalg.norm(image_float[1:, :, :] - image_float[:-1, :, :], axis=2),
            axis=1,
        )
        length = height
    else:
        diffs = np.mean(
            np.linalg.norm(image_float[:, 1:, :] - image_float[:, :-1, :], axis=2),
            axis=0,
        )
        length = width

    if len(diffs) < 12:
        return None

    edge_ignore = max(2, int(len(diffs) * 0.06))
    usable = diffs[edge_ignore : len(diffs) - edge_ignore]

    if usable.size == 0:
        return None

    max_local_index = int(np.argmax(usable))
    max_score = float(usable[max_local_index])
    max_index = max_local_index + edge_ignore
    baseline = float(np.percentile(usable, 92))

    if baseline <= 0:
        return None

    is_strong_outlier = max_score >= baseline * 2.4
    is_strong_absolute = max_score >= 38.0

    if is_strong_outlier and is_strong_absolute:
        return max_index / length, max_score, baseline

    return None


def build_large_region_candidates(
    image_array: np.ndarray,
) -> list[tuple[str, np.ndarray, np.ndarray, np.ndarray]]:
    height, width = image_array.shape[:2]

    top_end = int(height * 0.35)
    bottom_start = int(height * 0.65)
    left_end = int(width * 0.35)
    right_start = int(width * 0.65)

    return [
        (
            "top",
            image_array[:top_end, :],
            image_array[top_end : min(height, int(height * 0.70)), :],
            image_array[max(0, top_end - 2) : min(height, top_end + 2), :],
        ),
        (
            "bottom",
            image_array[bottom_start:, :],
            image_array[max(0, int(height * 0.30)) : bottom_start, :],
            image_array[max(0, bottom_start - 2) : min(height, bottom_start + 2), :],
        ),
        (
            "left",
            image_array[:, :left_end],
            image_array[:, left_end : min(width, int(width * 0.70))],
            image_array[:, max(0, left_end - 2) : min(width, left_end + 2)],
        ),
        (
            "right",
            image_array[:, right_start:],
            image_array[:, max(0, int(width * 0.30)) : right_start],
            image_array[:, max(0, right_start - 2) : min(width, right_start + 2)],
        ),
        (
            "top_half",
            image_array[: height // 2, :],
            image_array[height // 2 :, :],
            image_array[max(0, height // 2 - 2) : min(height, height // 2 + 2), :],
        ),
        (
            "bottom_half",
            image_array[height // 2 :, :],
            image_array[: height // 2, :],
            image_array[max(0, height // 2 - 2) : min(height, height // 2 + 2), :],
        ),
        (
            "left_half",
            image_array[:, : width // 2],
            image_array[:, width // 2 :],
            image_array[:, max(0, width // 2 - 2) : min(width, width // 2 + 2)],
        ),
        (
            "right_half",
            image_array[:, width // 2 :],
            image_array[:, : width // 2],
            image_array[:, max(0, width // 2 - 2) : min(width, width // 2 + 2)],
        ),
    ]


def calculate_area_ratio(region: np.ndarray, full_width: int, full_height: int) -> float:
    region_height, region_width = region.shape[:2]
    full_area = full_width * full_height

    if full_area <= 0:
        return 0.0

    return (region_width * region_height) / full_area


def calculate_dominant_color_ratio(image_array: np.ndarray) -> float:
    if image_array.size == 0:
        return 0.0

    small = cv2.resize(image_array, (80, 80), interpolation=cv2.INTER_AREA)
    quantized = (small // 24).astype(np.uint8)
    flat = quantized.reshape(-1, 3)

    _, counts = np.unique(flat, axis=0, return_counts=True)

    return float(np.max(counts) / np.sum(counts))


def calculate_mean_color_difference(first: np.ndarray, second: np.ndarray) -> float:
    if first.size == 0 or second.size == 0:
        return 0.0

    first_mean = np.mean(first.reshape(-1, 3), axis=0)
    second_mean = np.mean(second.reshape(-1, 3), axis=0)

    return float(np.linalg.norm(first_mean - second_mean))


def split_into_grid(image_array: np.ndarray, grid_size: int) -> list[np.ndarray]:
    height, width = image_array.shape[:2]

    if width < grid_size or height < grid_size:
        return []

    blocks: list[np.ndarray] = []

    for row in range(grid_size):
        for column in range(grid_size):
            top = int(row * height / grid_size)
            bottom = int((row + 1) * height / grid_size)
            left = int(column * width / grid_size)
            right = int((column + 1) * width / grid_size)

            block = image_array[top:bottom, left:right]

            if block.size > 0:
                blocks.append(block)

    return blocks


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