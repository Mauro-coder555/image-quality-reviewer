from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError

from src.settings import ALLOWED_EXTENSIONS, BLUR_THRESHOLD, MIN_HEIGHT, MIN_WIDTH


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
        width, height, blur_score = inspect_image_file(path)

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


def inspect_image_file(path: Path) -> tuple[int, int, float]:
    with Image.open(path) as image:
        image.load()

        width, height = image.size
        blur_score = calculate_blur_score(image)

        return width, height, blur_score


def calculate_blur_score(image: Image.Image) -> float:
    grayscale_image = image.convert("L")

    # Resize very large images only for analysis speed. This does not modify the original file.
    grayscale_image.thumbnail((800, 800))

    edge_image = grayscale_image.filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(edge_image)

    # Variance of edge intensity is a simple blur proxy for the MVP.
    # Sharp images usually produce stronger edge variation.
    return float(stat.var[0])