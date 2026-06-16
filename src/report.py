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
    critical_files = [result for result in results if result.critical_reasons]
    warning_files = [result for result in results if result.warning_reasons and not result.critical_reasons]

    lines = [
        "# Image Quality Review Report",
        "",
        f"- Scan date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Selected folder: `{selected_folder}`",
        f"- Listed files in report: {total_files}",
        f"- Critical files: {len(critical_files)}",
        f"- Warning-only files: {len(warning_files)}",
        "",
        "## Listed images",
        "",
    ]

    if not results:
        lines.append("No listed images were found.")
    else:
        lines.extend(
            [
                "| File | Severity | Dimensions | Blur score | Status | Marked for deletion | Reasons |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )

        for result in results:
            dimensions = format_dimensions(result)
            blur_score = format_blur_score(result)
            reasons = format_reasons(result)

            lines.append(
                f"| `{result.path}` | {result.severity} | {dimensions} | {blur_score} | "
                f"{result.status} | {result.marked_for_deletion} | {reasons} |"
            )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "This report is generated locally.",
            "Critical means the image may be corrupted, incomplete, glitched, or technically damaged.",
            "Warnings such as low resolution or blur do not necessarily mean the image is unusable.",
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


def format_reasons(result: ImageAnalysisResult) -> str:
    sections: list[str] = []

    if result.critical_reasons:
        sections.append("Critical: " + "; ".join(result.critical_reasons))

    if result.warning_reasons:
        sections.append("Warnings: " + "; ".join(result.warning_reasons))

    if result.info_reasons:
        sections.append("Info: " + "; ".join(result.info_reasons))

    if not sections:
        return "No issues"

    return " / ".join(sections)