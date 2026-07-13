import argparse
import json
from collections import Counter
from pathlib import Path

from src.analyzer import analyze_image
from src.models import ImageResult, ImageStatus
from src.validator import SUPPORTED_EXTENSIONS, validate_image


def determine_status(result: ImageResult) -> ImageStatus:
    severities = {evidence.severity for evidence in result.evidence if not evidence.passed}

    if "broken" in severities:
        return ImageStatus.BROKEN

    if "review" in severities:
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
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def print_result(result: ImageResult) -> None:
    symbol = {
        ImageStatus.OK: "[OK]",
        ImageStatus.REVIEW: "[REVIEW]",
        ImageStatus.BROKEN: "[BROKEN]",
    }[result.status]

    print(f"{symbol} {result.path}")

    for evidence in result.evidence:
        if not evidence.passed:
            print(f"    - {evidence.message}")


def save_report(results: list[ImageResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "summary": dict(Counter(result.status.value for result in results)),
        "images": [result.to_dict() for result in results],
    }

    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detecta imágenes corruptas o sospechosas."
    )

    parser.add_argument(
        "folder",
        type=Path,
        help="Carpeta que contiene las imágenes.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/report.json"),
        help="Ruta del reporte JSON.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    folder: Path = args.folder
    output_path: Path = args.output

    if not folder.exists():
        raise SystemExit(f"La carpeta no existe: {folder}")

    if not folder.is_dir():
        raise SystemExit(f"La ruta no es una carpeta: {folder}")

    images = find_images(folder)

    if not images:
        print("No se encontraron imágenes compatibles.")
        return

    results: list[ImageResult] = []

    for image_path in images:
        result = process_image(image_path)
        results.append(result)
        print_result(result)

    save_report(results, output_path)

    summary = Counter(result.status.value for result in results)

    print()
    print("Resumen")
    print("-------")
    print(f"OK: {summary.get(ImageStatus.OK.value, 0)}")
    print(f"Review: {summary.get(ImageStatus.REVIEW.value, 0)}")
    print(f"Broken: {summary.get(ImageStatus.BROKEN.value, 0)}")
    print(f"Reporte: {output_path.resolve()}")


if __name__ == "__main__":
    main()