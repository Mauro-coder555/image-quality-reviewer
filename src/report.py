from datetime import datetime
from pathlib import Path

from src.image_analysis import ImageAnalysisResult
from src.settings import REPORTS_DIR


def generate_markdown_report(
    selected_folder: Path,
    results: list[ImageAnalysisResult],
    reports_dir: Path = REPORTS_DIR,
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = reports_dir / f"image_quality_report_{timestamp}.md"

    total_files = len(results)
    problematic_files = [result for result in results if result.is_problematic]

    lines = [
        "# Image Quality Review Report",
        "",
        f"- Scan date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Selected folder: `{selected_folder}`",
        f"- Total image files scanned: {total_files}",
        f"- Problematic files found: {len(problematic_files)}",
        "",
        "## Problematic images",
        "",
    ]

    if not problematic_files:
        lines.append("No problematic images were found.")
    else:
        lines.extend(
            [
                "| File | Dimensions | Blur score | Status | Marked for deletion | Reasons |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )

        for result in problematic_files:
            dimensions = format_dimensions(result)
            blur_score = format_blur_score(result)
            reasons = "; ".join(result.reasons)

            lines.append(
                f"| `{result.path}` | {dimensions} | {blur_score} | "
                f"{result.status} | {result.marked_for_deletion} | {reasons} |"
            )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "This report is generated locally.",
            "The tool does not upload images, does not modify original images, and does not replace human review.",
            "",
        ]
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")

    return report_path


def format_dimensions(result: ImageAnalysisResult) -> str:
    if result.width is None or result.height is None:
        return "not available"

    return f"{result.width}x{result.height}"


def format_blur_score(result: ImageAnalysisResult) -> str:
    if result.blur_score is None:
        return "not available"

    return f"{result.blur_score:.2f}"