from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageFile, ImageFilter, ImageStat, UnidentifiedImageError

from src.ml_corruption_classifier import classify_image_with_ml
from src.settings import (
    ALLOWED_EXTENSIONS,
    BLUR_THRESHOLD,
    CHECK_FORMAT_EXTENSION_MISMATCH,
    EXTENSION_TO_PIL_FORMATS,
    ISSUE_WEIGHTS,
    MIN_BYTES_PER_MEGA_PIXEL,
    MIN_FILE_SIZE_BYTES,
    MIN_HEIGHT,
    MIN_WIDTH,
)


@dataclass
class ImageAnalysisResult:
    path: Path
    is_problematic: bool
    critical_reasons: list[str] = field(default_factory=list)
    suspect_reasons: list[str] = field(default_factory=list)
    warning_reasons: list[str] = field(default_factory=list)
    info_reasons: list[str] = field(default_factory=list)
    issue_codes: list[str] = field(default_factory=list)
    score: int = 0
    width: int | None = None
    height: int | None = None
    blur_score: float | None = None
    metrics: dict[str, object] = field(default_factory=dict)
    status: str = "pending"
    marked_for_deletion: bool = False

    @property
    def severity(self) -> str:
        if self.critical_reasons:
            return "broken"
        if self.suspect_reasons:
            return "suspect"
        if self.warning_reasons:
            return "warning"
        if self.info_reasons:
            return "info"
        return "ok"

    @property
    def issue_type(self) -> str:
        if self.critical_reasons:
            return "Broken"
        if self.suspect_reasons:
            return "Suspect"
        if self.warning_reasons:
            return "Review"
        if self.info_reasons:
            return "Info"
        return "OK"

    @property
    def reasons(self) -> list[str]:
        return (
            self.critical_reasons
            + self.suspect_reasons
            + self.warning_reasons
            + self.info_reasons
        )


def analyze_image(path: Path) -> ImageAnalysisResult:
    result = ImageAnalysisResult(
        path=path,
        is_problematic=False,
        status="analyzed",
    )

    add_file_basic_checks(result)

    if result.critical_reasons:
        finalize_result(result)
        return result

    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        add_warning(result, "unsupported_format", "Unsupported image format")
        finalize_result(result)
        return result

    try:
        structure_issue_codes = detect_file_structure_issues(path)

        verify_image_file(path)

        width, height, image_format, blur_score, image = decode_image_file(path)

        result.width = width
        result.height = height
        result.blur_score = blur_score
        result.metrics["image_format"] = image_format

        add_structure_issues(result, structure_issue_codes)
        add_dimension_checks(result, width, height)
        add_blur_info(result, blur_score)
        add_format_extension_mismatch(result, path, image_format)
        add_suspicious_file_size_warning(result, path, width, height)

        add_ml_classification(result, image)

        finalize_result(result)

    except UnidentifiedImageError:
        add_critical(result, "not_an_image", "Image cannot be opened")
        finalize_result(result)

    except OSError as error:
        add_critical(result, "decode_failed", f"Read error or possibly incomplete file: {error}")
        finalize_result(result)

    except Exception as error:
        add_critical(result, "unexpected_error", f"Unexpected analysis error: {error}")
        finalize_result(result)

    return result


def add_file_basic_checks(result: ImageAnalysisResult) -> None:
    path = result.path

    if not path.exists():
        add_critical(result, "file_missing", "File does not exist")
        return

    if not path.is_file():
        add_critical(result, "file_missing", "Path is not a file")
        return

    try:
        file_size = path.stat().st_size
        result.metrics["file_size_bytes"] = file_size
    except OSError:
        add_warning(result, "file_size_unavailable", "File size could not be read")
        return

    if file_size == 0:
        add_critical(result, "file_empty", "Empty file")
        return

    if file_size < MIN_FILE_SIZE_BYTES:
        add_warning(result, "file_too_small", f"File is very small: {file_size} bytes")


def verify_image_file(path: Path) -> None:
    with Image.open(path) as image:
        image.verify()


def decode_image_file(path: Path) -> tuple[int, int, str | None, float, Image.Image]:
    previous_setting = ImageFile.LOAD_TRUNCATED_IMAGES
    ImageFile.LOAD_TRUNCATED_IMAGES = False

    try:
        with Image.open(path) as image:
            image_format = image.format
            image.load()
            rgb_image = image.convert("RGB")

        width, height = rgb_image.size
        blur_score = calculate_blur_score(rgb_image)

        return width, height, image_format, blur_score, rgb_image

    finally:
        ImageFile.LOAD_TRUNCATED_IMAGES = previous_setting


def calculate_blur_score(image: Image.Image) -> float:
    grayscale_image = image.convert("L")
    grayscale_image.thumbnail((800, 800))

    edge_image = grayscale_image.filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(edge_image)

    return float(stat.var[0])


def detect_file_structure_issues(path: Path) -> set[str]:
    issue_codes: set[str] = set()

    try:
        file_size = path.stat().st_size
    except OSError:
        issue_codes.add("file_size_unavailable")
        return issue_codes

    suffix = path.suffix.lower()

    try:
        with path.open("rb") as file:
            if suffix in {".jpg", ".jpeg"}:
                issue_codes.update(validate_jpeg_structure(file, file_size))
            elif suffix == ".png":
                issue_codes.update(validate_png_structure(file, file_size))
            elif suffix == ".webp":
                issue_codes.update(validate_webp_structure(file, file_size))
            elif suffix == ".bmp":
                issue_codes.update(validate_bmp_structure(file, file_size))
    except OSError:
        issue_codes.add("structure_check_failed")

    return issue_codes


def validate_jpeg_structure(file: BinaryIO, file_size: int) -> set[str]:
    issue_codes: set[str] = set()

    if file_size < 4:
        issue_codes.add("jpeg_missing_eof")
        return issue_codes

    file.seek(0)
    start_bytes = file.read(2)

    file.seek(-2, 2)
    end_bytes = file.read(2)

    if start_bytes != b"\xff\xd8":
        issue_codes.add("invalid_jpeg_header")

    if end_bytes != b"\xff\xd9":
        issue_codes.add("jpeg_missing_eof")

    return issue_codes


def validate_png_structure(file: BinaryIO, file_size: int) -> set[str]:
    issue_codes: set[str] = set()
    png_signature = b"\x89PNG\r\n\x1a\n"

    if file_size < len(png_signature) + 12:
        issue_codes.add("png_missing_iend")
        return issue_codes

    file.seek(0)
    start_bytes = file.read(len(png_signature))

    if start_bytes != png_signature:
        issue_codes.add("invalid_png_header")

    file.seek(-32, 2)
    ending_chunk = file.read(32)

    if b"IEND" not in ending_chunk:
        issue_codes.add("png_missing_iend")

    return issue_codes


def validate_webp_structure(file: BinaryIO, file_size: int) -> set[str]:
    issue_codes: set[str] = set()

    if file_size < 12:
        issue_codes.add("webp_size_mismatch")
        return issue_codes

    file.seek(0)
    header = file.read(12)

    if not header.startswith(b"RIFF") or header[8:12] != b"WEBP":
        issue_codes.add("invalid_webp_header")
        return issue_codes

    declared_size = int.from_bytes(header[4:8], byteorder="little", signed=False) + 8

    if declared_size > file_size + 2:
        issue_codes.add("webp_size_mismatch")

    return issue_codes


def validate_bmp_structure(file: BinaryIO, file_size: int) -> set[str]:
    issue_codes: set[str] = set()

    if file_size < 26:
        issue_codes.add("bmp_size_mismatch")
        return issue_codes

    file.seek(0)
    header = file.read(6)

    if not header.startswith(b"BM"):
        issue_codes.add("invalid_bmp_header")
        return issue_codes

    declared_size = int.from_bytes(header[2:6], byteorder="little", signed=False)

    if declared_size > 0 and declared_size > file_size:
        issue_codes.add("bmp_size_mismatch")

    return issue_codes


def add_structure_issues(result: ImageAnalysisResult, issue_codes: set[str]) -> None:
    messages = {
        "invalid_jpeg_header": "Invalid JPEG header",
        "jpeg_missing_eof": "JPEG is missing EOF marker FF D9. It may be truncated.",
        "invalid_png_header": "Invalid PNG header",
        "png_missing_iend": "PNG is missing IEND chunk. It may be incomplete.",
        "invalid_webp_header": "Invalid WEBP header",
        "webp_size_mismatch": "WEBP declared size is larger than actual file size.",
        "invalid_bmp_header": "Invalid BMP header",
        "bmp_size_mismatch": "BMP declared size is larger than actual file size.",
        "structure_check_failed": "File structure could not be checked.",
    }

    for issue_code in sorted(issue_codes):
        message = messages.get(issue_code, issue_code)

        if issue_code.startswith("invalid_"):
            add_critical(result, issue_code, message)
        else:
            add_warning(result, issue_code, message)


def add_dimension_checks(result: ImageAnalysisResult, width: int, height: int) -> None:
    if width <= 0 or height <= 0:
        add_critical(result, "invalid_dimensions", "Invalid image dimensions")
        return

    if width < MIN_WIDTH or height < MIN_HEIGHT:
        add_info(result, "dimensions_too_small", f"Low resolution: {width}x{height}")

    aspect_ratio = max(width / height, height / width)
    result.metrics["aspect_ratio"] = round(aspect_ratio, 4)


def add_blur_info(result: ImageAnalysisResult, blur_score: float) -> None:
    result.metrics["blur_score"] = round(blur_score, 4)

    if blur_score < BLUR_THRESHOLD:
        add_info(result, "possible_blur", f"Possible blur detected: score {blur_score:.2f}")


def add_format_extension_mismatch(
    result: ImageAnalysisResult,
    path: Path,
    image_format: str | None,
) -> None:
    if not CHECK_FORMAT_EXTENSION_MISMATCH:
        return

    if image_format is None:
        return

    expected_formats = EXTENSION_TO_PIL_FORMATS.get(path.suffix.lower())

    if not expected_formats:
        return

    if image_format.upper() not in expected_formats:
        add_warning(
            result,
            "format_extension_mismatch",
            f"Format mismatch: extension is {path.suffix.lower()} but detected format is {image_format}",
        )


def add_suspicious_file_size_warning(
    result: ImageAnalysisResult,
    path: Path,
    width: int,
    height: int,
) -> None:
    if width <= 0 or height <= 0:
        return

    try:
        file_size_bytes = path.stat().st_size
    except OSError:
        return

    mega_pixels = (width * height) / 1_000_000

    if mega_pixels <= 0:
        return

    bytes_per_mega_pixel = file_size_bytes / mega_pixels
    result.metrics["bytes_per_megapixel"] = round(bytes_per_mega_pixel, 2)

    if bytes_per_mega_pixel < MIN_BYTES_PER_MEGA_PIXEL:
        add_warning(
            result,
            "suspicious_file_size",
            f"Suspiciously small file size for dimensions ({bytes_per_mega_pixel:.0f} bytes per megapixel)",
        )


def add_ml_classification(result: ImageAnalysisResult, image: Image.Image) -> None:
    ml_result = classify_image_with_ml(image)

    result.metrics["ml_model_available"] = ml_result.model_available
    result.metrics["ml_probability_broken"] = round(ml_result.probability_broken, 6)

    if not ml_result.model_available:
        add_info(result, "ml_model_missing", ml_result.reason)
        return

    if ml_result.status == "broken":
        add_critical(result, "ml_corruption_broken", ml_result.reason)
        return

    if ml_result.status == "suspect":
        add_suspect(result, "ml_corruption_suspect", ml_result.reason)
        return

    add_info(result, "ml_corruption_ok", ml_result.reason)


def add_critical(result: ImageAnalysisResult, code: str, message: str) -> None:
    result.critical_reasons.append(message)
    add_issue_code(result, code)


def add_suspect(result: ImageAnalysisResult, code: str, message: str) -> None:
    result.suspect_reasons.append(message)
    add_issue_code(result, code)


def add_warning(result: ImageAnalysisResult, code: str, message: str) -> None:
    result.warning_reasons.append(message)
    add_issue_code(result, code)


def add_info(result: ImageAnalysisResult, code: str, message: str) -> None:
    result.info_reasons.append(message)
    add_issue_code(result, code)


def add_issue_code(result: ImageAnalysisResult, code: str) -> None:
    result.issue_codes.append(code)
    result.score += ISSUE_WEIGHTS.get(code, 0)


def finalize_result(result: ImageAnalysisResult) -> None:
    result.critical_reasons = remove_duplicate_reasons(result.critical_reasons)
    result.suspect_reasons = remove_duplicate_reasons(result.suspect_reasons)
    result.warning_reasons = remove_duplicate_reasons(result.warning_reasons)
    result.info_reasons = remove_duplicate_reasons(result.info_reasons)
    result.issue_codes = remove_duplicate_reasons(result.issue_codes)

    result.status = result.severity
    result.is_problematic = bool(result.critical_reasons or result.suspect_reasons)


def remove_duplicate_reasons(reasons: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_reasons: list[str] = []

    for reason in reasons:
        if reason not in seen:
            unique_reasons.append(reason)
            seen.add(reason)

    return unique_reasons