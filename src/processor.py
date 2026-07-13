from pathlib import Path

from src.analyzer import analyze_image
from src.models import ImageResult, ImageStatus
from src.validator import SUPPORTED_EXTENSIONS, validate_image


def determine_status(result: ImageResult) -> ImageStatus:
    failed_severities = {
        evidence.severity
        for evidence in result.evidence
        if not evidence.passed
    }

    if "broken" in failed_severities:
        return ImageStatus.BROKEN

    if "review" in failed_severities:
        return ImageStatus.REVIEW

    return ImageStatus.OK


def process_image(path: Path) -> ImageResult:
    result = validate_image(path)

    has_broken_evidence = any(
        not evidence.passed and evidence.severity == "broken"
        for evidence in result.evidence
    )

    if not has_broken_evidence:
        analyze_image(path, result)

    result.status = determine_status(result)

    return result


def find_images(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )