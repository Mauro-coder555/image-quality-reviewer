from pathlib import Path

from PIL import Image

from src.models import ImageStatus
from src.validator import validate_image


def test_valid_png(tmp_path: Path) -> None:
    image_path = tmp_path / "valid.png"

    image = Image.new(
        mode="RGB",
        size=(100, 100),
        color=(120, 80, 200),
    )
    image.save(image_path)

    result = validate_image(image_path)

    broken_errors = [
        evidence
        for evidence in result.evidence
        if not evidence.passed and evidence.severity == "broken"
    ]

    assert not broken_errors
    assert result.width == 100
    assert result.height == 100
    assert result.format == "PNG"


def test_empty_file_is_broken(tmp_path: Path) -> None:
    image_path = tmp_path / "empty.jpg"
    image_path.write_bytes(b"")

    result = validate_image(image_path)

    assert result.status == ImageStatus.BROKEN


def test_fake_image_is_detected(tmp_path: Path) -> None:
    image_path = tmp_path / "fake.jpg"
    image_path.write_text(
        "Esto no es una imagen.",
        encoding="utf-8",
    )

    result = validate_image(image_path)

    broken_errors = [
        evidence
        for evidence in result.evidence
        if not evidence.passed and evidence.severity == "broken"
    ]

    assert broken_errors