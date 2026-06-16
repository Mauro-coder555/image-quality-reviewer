from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError

from src.corruption_detection import detect_visual_corruption
from src.settings import (
    ALLOWED_EXTENSIONS,
    BLUR_THRESHOLD,
    CHECK_FORMAT_EXTENSION_MISMATCH,
    EXTENSION_TO_PIL_FORMATS,
    MIN_BYTES_PER_MEGA_PIXEL,
    MIN_HEIGHT,
    MIN_WIDTH,
)


@dataclass
class ImageAnalysisResult:
    path: Path
    is_problematic: bool
    critical_reasons: list[str] = field(default_factory=list)
    warning_reasons: list[str] = field(default_factory=list)
    info_reasons: list[str] = field(default_factory=list)
    width: int | None = None
    height: int | None = None
    blur_score: float | None = None
    status: str = "pending"
    marked_for_deletion: bool = False

    @property
    def severity(self) -> str:
        if self.critical_reasons:
            return "critical"
        if self.warning_reasons:
            return "warning"
        if self.info_reasons:
            return "info"
        return "ok"

    @property
    def issue_type(self) -> str:
        if self.critical_reasons:
            return "Unusable"
        if self.warning_reasons:
            return "Review"
        if self.info_reasons:
            return "Info"
        return "OK"

    @property
    def reasons(self) -> list[str]:
        return self.critical_reasons + self.warning_reasons + self.info_reasons


def analyze_image(path: Path) -> ImageAnalysisResult:
    result = ImageAnalysisResult(
        path=path,
        is_problematic=False,
        status="analyzed",
    )

    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        result.warning_reasons.append("Unsupported image format")
        result.status = "warning"
        return result

    if not path.exists():
        result.critical_reasons.append("File does not exist")
        result.is_problematic = True
        result.status = "critical"
        return result

    try:
        result.critical_reasons.extend(detect_file_structure_issues(path))

        verify_image_file(path)

        (
            width,
            height,
            image_format,
            blur_score,
            critical_reasons,
            warning_reasons,
            info_reasons,
        ) = inspect_image_file(path)

        result.width = width
        result.height = height
        result.blur_score = blur_score

        if width <= 0 or height <= 0:
            result.critical_reasons.append("Invalid image dimensions")

        if width < MIN_WIDTH or height < MIN_HEIGHT:
            result.info_reasons.append(f"Low resolution: {width}x{height}")

        if blur_score < BLUR_THRESHOLD:
            result.info_reasons.append(f"Possible blur detected: score {blur_score:.2f}")

        result.warning_reasons.extend(
            detect_format_extension_mismatch(path=path, image_format=image_format)
        )

        result.critical_reasons.extend(critical_reasons)
        result.warning_reasons.extend(warning_reasons)
        result.info_reasons.extend(info_reasons)

        result.critical_reasons = remove_duplicate_reasons(result.critical_reasons)
        result.warning_reasons = remove_duplicate_reasons(result.warning_reasons)
        result.info_reasons = remove_duplicate_reasons(result.info_reasons)

        result.is_problematic = bool(result.critical_reasons)
        result.status = result.severity

    except UnidentifiedImageError:
        result.critical_reasons.append("Image cannot be opened")
        result.is_problematic = True
        result.status = "critical"

    except OSError as error:
        result.critical_reasons.append(f"Read error or possibly incomplete file: {error}")
        result.is_problematic = True
        result.status = "critical"

    except Exception as error:
        result.critical_reasons.append(f"Unexpected analysis error: {error}")
        result.is_problematic = True
        result.status = "critical"

    return result


def verify_image_file(path: Path) -> None:
    with Image.open(path) as image:
        image.verify()


def inspect_image_file(
    path: Path,
) -> tuple[int, int, str | None, float, list[str], list[str], list[str]]:
    with Image.open(path) as image:
        image.load()

        width, height = image.size
        image_format = image.format
        blur_score = calculate_blur_score(image)

        corruption_result = detect_visual_corruption(image)

        critical_reasons = corruption_result.critical_reasons
        warning_reasons = corruption_result.warning_reasons
        info_reasons: list[str] = []

        warning_reasons.extend(
            detect_non_critical_quality_warnings(
                file_path=path,
                width=width,
                height=height,
            )
        )

        return (
            width,
            height,
            image_format,
            blur_score,
            critical_reasons,
            warning_reasons,
            info_reasons,
        )


def calculate_blur_score(image: Image.Image) -> float:
    grayscale_image = image.convert("L")
    grayscale_image.thumbnail((800, 800))

    edge_image = grayscale_image.filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(edge_image)

    return float(stat.var[0])


def detect_file_structure_issues(path: Path) -> list[str]:
    reasons: list[str] = []

    try:
        file_size = path.stat().st_size
    except OSError:
        return ["File size could not be read"]

    if file_size == 0:
        return ["Empty file"]

    suffix = path.suffix.lower()

    try:
        with path.open("rb") as file:
            if suffix in {".jpg", ".jpeg"}:
                reasons.extend(validate_jpeg_structure(file, file_size))
            elif suffix == ".png":
                reasons.extend(validate_png_structure(file, file_size))
            elif suffix == ".webp":
                reasons.extend(validate_webp_structure(file, file_size))
            elif suffix == ".bmp":
                reasons.extend(validate_bmp_structure(file, file_size))
    except OSError as error:
        reasons.append(f"File structure could not be checked: {error}")

    return reasons


def validate_jpeg_structure(file: BinaryIO, file_size: int) -> list[str]:
    if file_size < 4:
        return ["Possible incomplete JPEG file: file is too small"]

    reasons: list[str] = []

    file.seek(0)
    start_bytes = file.read(2)

    file.seek(-2, 2)
    end_bytes = file.read(2)

    if start_bytes != b"\xff\xd8":
        reasons.append("Invalid JPEG header")

    if end_bytes != b"\xff\xd9":
        reasons.append("Possible incomplete JPEG file: missing end marker")

    return reasons


def validate_png_structure(file: BinaryIO, file_size: int) -> list[str]:
    png_signature = b"\x89PNG\r\n\x1a\n"

    if file_size < len(png_signature) + 12:
        return ["Possible incomplete PNG file: file is too small"]

    reasons: list[str] = []

    file.seek(0)
    start_bytes = file.read(len(png_signature))

    if start_bytes != png_signature:
        reasons.append("Invalid PNG header")

    file.seek(-12, 2)
    ending_chunk = file.read(12)

    if b"IEND" not in ending_chunk:
        reasons.append("Possible incomplete PNG file: missing IEND chunk")

    return reasons


def validate_webp_structure(file: BinaryIO, file_size: int) -> list[str]:
    if file_size < 12:
        return ["Possible incomplete WEBP file: file is too small"]

    reasons: list[str] = []

    file.seek(0)
    header = file.read(12)

    if not header.startswith(b"RIFF") or header[8:12] != b"WEBP":
        reasons.append("Invalid WEBP header")
        return reasons

    declared_size = int.from_bytes(header[4:8], byteorder="little", signed=False) + 8

    if declared_size > file_size + 2:
        reasons.append("Possible incomplete WEBP file: declared size is larger than actual file size")

    return reasons


def validate_bmp_structure(file: BinaryIO, file_size: int) -> list[str]:
    if file_size < 26:
        return ["Possible incomplete BMP file: file is too small"]

    reasons: list[str] = []

    file.seek(0)
    header = file.read(6)

    if not header.startswith(b"BM"):
        reasons.append("Invalid BMP header")
        return reasons

    declared_size = int.from_bytes(header[2:6], byteorder="little", signed=False)

    if declared_size > 0 and declared_size > file_size:
        reasons.append("Possible incomplete BMP file: declared size is larger than actual file size")

    return reasons


def detect_format_extension_mismatch(path: Path, image_format: str | None) -> list[str]:
    if not CHECK_FORMAT_EXTENSION_MISMATCH:
        return []

    if image_format is None:
        return []

    expected_formats = EXTENSION_TO_PIL_FORMATS.get(path.suffix.lower())

    if not expected_formats:
        return []

    if image_format.upper() not in expected_formats:
        return [
            f"Format mismatch: file extension is {path.suffix.lower()} "
            f"but detected format is {image_format}"
        ]

    return []


def detect_non_critical_quality_warnings(
    file_path: Path,
    width: int,
    height: int,
) -> list[str]:
    warnings: list[str] = []

    warnings.extend(detect_suspicious_file_size(file_path, width, height))

    return warnings


def detect_suspicious_file_size(file_path: Path, width: int, height: int) -> list[str]:
    if width <= 0 or height <= 0:
        return []

    try:
        file_size_bytes = file_path.stat().st_size
    except OSError:
        return ["File size could not be read"]

    mega_pixels = (width * height) / 1_000_000

    if mega_pixels <= 0:
        return []

    bytes_per_mega_pixel = file_size_bytes / mega_pixels

    if bytes_per_mega_pixel < MIN_BYTES_PER_MEGA_PIXEL:
        return [
            f"Suspiciously small file size for dimensions "
            f"({bytes_per_mega_pixel:.0f} bytes per megapixel)"
        ]

    return []


def remove_duplicate_reasons(reasons: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_reasons: list[str] = []

    for reason in reasons:
        if reason not in seen:
            unique_reasons.append(reason)
            seen.add(reason)

    return unique_reasons