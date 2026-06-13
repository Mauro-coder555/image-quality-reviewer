from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError

from src.settings import (
    ALLOWED_EXTENSIONS,
    ARTIFACT_ANALYSIS_MAX_SIZE,
    ARTIFACT_GRID_SIZE,
    BLUR_THRESHOLD,
    LOW_VARIANCE_BLOCK_THRESHOLD,
    MAX_GRAY_CHANNEL_DIFFERENCE,
    MAX_LOW_VARIANCE_BLOCK_RATIO,
    MAX_SOLID_COLOR_RATIO,
    MIN_BYTES_PER_MEGA_PIXEL,
    MIN_HEIGHT,
    MIN_WIDTH,
    NEAR_BLACK_THRESHOLD,
    NEAR_WHITE_THRESHOLD,
)


@dataclass
class ImageAnalysisResult:
    path: Path
    is_problematic: bool
    reasons: list[str] = field(default_factory=list)
    width: int | None = None
    height: int | None = None
    blur_score: float | None = None
    status: str = "pending"
    marked_for_deletion: bool = False


def analyze_image(path: Path) -> ImageAnalysisResult:
    result = ImageAnalysisResult(
        path=path,
        is_problematic=False,
        status="analyzed",
    )

    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        result.is_problematic = True
        result.reasons.append("Unsupported image format")
        result.status = "cannot be analyzed"
        return result

    if not path.exists():
        result.is_problematic = True
        result.reasons.append("File does not exist")
        result.status = "cannot be analyzed"
        return result

    try:
        verify_image_file(path)
        width, height, blur_score, artifact_reasons = inspect_image_file(path)

        result.width = width
        result.height = height
        result.blur_score = blur_score

        if width <= 0 or height <= 0:
            result.is_problematic = True
            result.reasons.append("Invalid image dimensions")

        if width < MIN_WIDTH or height < MIN_HEIGHT:
            result.is_problematic = True
            result.reasons.append(f"Low resolution: {width}x{height}")

        if blur_score < BLUR_THRESHOLD:
            result.is_problematic = True
            result.reasons.append(f"High blur detected: score {blur_score:.2f}")

        if artifact_reasons:
            result.is_problematic = True
            result.reasons.extend(artifact_reasons)

        if not result.reasons:
            result.status = "ok"

    except UnidentifiedImageError:
        result.is_problematic = True
        result.reasons.append("Image cannot be opened")
        result.status = "cannot be analyzed"

    except OSError as error:
        result.is_problematic = True
        result.reasons.append(f"Read error or possibly incomplete file: {error}")
        result.status = "cannot be analyzed"

    except Exception as error:
        result.is_problematic = True
        result.reasons.append(f"Unexpected analysis error: {error}")
        result.status = "cannot be analyzed"

    return result


def verify_image_file(path: Path) -> None:
    with Image.open(path) as image:
        image.verify()


def inspect_image_file(path: Path) -> tuple[int, int, float, list[str]]:
    with Image.open(path) as image:
        image.load()

        width, height = image.size
        blur_score = calculate_blur_score(image)
        artifact_reasons = detect_possible_visual_artifacts(
            image=image,
            file_path=path,
            width=width,
            height=height,
        )

        return width, height, blur_score, artifact_reasons


def calculate_blur_score(image: Image.Image) -> float:
    grayscale_image = image.convert("L")

    # Resize very large images only for analysis speed. This does not modify the original file.
    grayscale_image.thumbnail((800, 800))

    edge_image = grayscale_image.filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(edge_image)

    # Variance of edge intensity is a simple blur proxy for the MVP.
    # Sharp images usually produce stronger edge variation.
    return float(stat.var[0])


def detect_possible_visual_artifacts(
    image: Image.Image,
    file_path: Path,
    width: int,
    height: int,
) -> list[str]:
    reasons: list[str] = []

    solid_color_reasons = detect_large_solid_color_areas(image)
    low_variance_reasons = detect_low_variance_blocks(image)
    file_size_reasons = detect_suspicious_file_size(file_path, width, height)

    reasons.extend(solid_color_reasons)
    reasons.extend(low_variance_reasons)
    reasons.extend(file_size_reasons)

    return reasons


def detect_large_solid_color_areas(image: Image.Image) -> list[str]:
    sample_image = image.copy()
    sample_image.thumbnail((ARTIFACT_ANALYSIS_MAX_SIZE, ARTIFACT_ANALYSIS_MAX_SIZE))
    rgb_image = sample_image.convert("RGB")

    pixels = list(rgb_image.getdata())
    total_pixels = len(pixels)

    if total_pixels == 0:
        return ["Possible damaged image: no readable pixels found"]

    near_black_count = 0
    near_white_count = 0
    near_gray_count = 0

    for red, green, blue in pixels:
        if max(red, green, blue) <= NEAR_BLACK_THRESHOLD:
            near_black_count += 1
            continue

        if min(red, green, blue) >= NEAR_WHITE_THRESHOLD:
            near_white_count += 1
            continue

        channel_difference = max(red, green, blue) - min(red, green, blue)

        if channel_difference <= MAX_GRAY_CHANNEL_DIFFERENCE:
            near_gray_count += 1

    near_black_ratio = near_black_count / total_pixels
    near_white_ratio = near_white_count / total_pixels
    near_gray_ratio = near_gray_count / total_pixels

    reasons: list[str] = []

    if near_black_ratio > MAX_SOLID_COLOR_RATIO:
        reasons.append(
            f"Possible visual artifact: large near-black area "
            f"({near_black_ratio:.0%} of sampled pixels)"
        )

    if near_white_ratio > MAX_SOLID_COLOR_RATIO:
        reasons.append(
            f"Possible visual artifact: large near-white area "
            f"({near_white_ratio:.0%} of sampled pixels)"
        )

    if near_gray_ratio > MAX_SOLID_COLOR_RATIO:
        reasons.append(
            f"Possible visual artifact: large near-gray area "
            f"({near_gray_ratio:.0%} of sampled pixels)"
        )

    return reasons


def detect_low_variance_blocks(image: Image.Image) -> list[str]:
    sample_image = image.copy()
    sample_image.thumbnail((ARTIFACT_ANALYSIS_MAX_SIZE, ARTIFACT_ANALYSIS_MAX_SIZE))
    grayscale_image = sample_image.convert("L")

    width, height = grayscale_image.size

    if width < ARTIFACT_GRID_SIZE or height < ARTIFACT_GRID_SIZE:
        return []

    block_width = max(1, width // ARTIFACT_GRID_SIZE)
    block_height = max(1, height // ARTIFACT_GRID_SIZE)

    total_blocks = 0
    low_variance_blocks = 0

    for row in range(ARTIFACT_GRID_SIZE):
        for column in range(ARTIFACT_GRID_SIZE):
            left = column * block_width
            upper = row * block_height
            right = width if column == ARTIFACT_GRID_SIZE - 1 else left + block_width
            lower = height if row == ARTIFACT_GRID_SIZE - 1 else upper + block_height

            block = grayscale_image.crop((left, upper, right, lower))
            stat = ImageStat.Stat(block)
            variance = float(stat.var[0])

            total_blocks += 1

            if variance <= LOW_VARIANCE_BLOCK_THRESHOLD:
                low_variance_blocks += 1

    if total_blocks == 0:
        return []

    low_variance_ratio = low_variance_blocks / total_blocks

    if low_variance_ratio > MAX_LOW_VARIANCE_BLOCK_RATIO:
        return [
            f"Possible visual artifact: too many flat or uniform blocks "
            f"({low_variance_ratio:.0%} of sampled blocks)"
        ]

    return []


def detect_suspicious_file_size(file_path: Path, width: int, height: int) -> list[str]:
    if width <= 0 or height <= 0:
        return []

    try:
        file_size_bytes = file_path.stat().st_size
    except OSError:
        return ["Possible damaged image: file size could not be read"]

    mega_pixels = (width * height) / 1_000_000

    if mega_pixels <= 0:
        return []

    bytes_per_mega_pixel = file_size_bytes / mega_pixels

    if bytes_per_mega_pixel < MIN_BYTES_PER_MEGA_PIXEL:
        return [
            f"Possible incomplete or damaged image: suspiciously small file size "
            f"({bytes_per_mega_pixel:.0f} bytes per megapixel)"
        ]

    return []