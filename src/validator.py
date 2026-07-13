from pathlib import Path

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

from src.models import ImageResult, ImageStatus


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}


MAGIC_NUMBERS = {
    "JPEG": (b"\xff\xd8\xff",),
    "PNG": (b"\x89PNG\r\n\x1a\n",),
    "WEBP": (b"RIFF",),
    "BMP": (b"BM",),
    "TIFF": (b"II*\x00", b"MM\x00*"),
}


def detect_magic_number(path: Path) -> str | None:
    try:
        with path.open("rb") as file:
            header = file.read(16)
    except OSError:
        return None

    for image_format, signatures in MAGIC_NUMBERS.items():
        if any(header.startswith(signature) for signature in signatures):
            if image_format == "WEBP":
                if len(header) >= 12 and header[8:12] == b"WEBP":
                    return "WEBP"
                continue

            return image_format

    return None


def validate_jpeg_ending(path: Path, result: ImageResult) -> None:
    if path.suffix.lower() not in {".jpg", ".jpeg"}:
        return

    try:
        with path.open("rb") as file:
            file.seek(-2, 2)
            ending = file.read(2)
    except (OSError, ValueError) as exc:
        result.add_evidence(
            check="jpeg_ending",
            passed=False,
            severity="broken",
            message="No fue posible leer el final del archivo JPEG.",
            error=str(exc),
        )
        return

    if ending == b"\xff\xd9":
        result.add_evidence(
            check="jpeg_ending",
            passed=True,
            severity="info",
            message="El JPEG contiene el marcador final FFD9.",
        )
    else:
        result.add_evidence(
            check="jpeg_ending",
            passed=False,
            severity="review",
            message=(
                "El JPEG no termina con FFD9. Puede estar truncado, "
                "aunque algunos archivos válidos contienen datos adicionales."
            ),
        )


def validate_png_ending(path: Path, result: ImageResult) -> None:
    if path.suffix.lower() != ".png":
        return

    try:
        with path.open("rb") as file:
            content = file.read()
    except OSError as exc:
        result.add_evidence(
            check="png_iend",
            passed=False,
            severity="broken",
            message="No fue posible leer el archivo PNG.",
            error=str(exc),
        )
        return

    if content.endswith(b"IEND\xaeB`\x82"):
        result.add_evidence(
            check="png_iend",
            passed=True,
            severity="info",
            message="El PNG contiene un chunk IEND válido al final.",
        )
    else:
        result.add_evidence(
            check="png_iend",
            passed=False,
            severity="review",
            message="No se encontró el final estándar IEND del PNG.",
        )


def validate_with_pillow(path: Path, result: ImageResult) -> None:
    try:
        with Image.open(path) as image:
            detected_format = image.format
            image.verify()

        result.add_evidence(
            check="pillow_verify",
            passed=True,
            severity="info",
            message="Pillow verificó la estructura del archivo.",
        )

        with Image.open(path) as image:
            image.load()

            result.width = image.width
            result.height = image.height
            result.format = image.format or detected_format

        result.add_evidence(
            check="pillow_load",
            passed=True,
            severity="info",
            message="Pillow pudo decodificar todos los píxeles.",
            width=result.width,
            height=result.height,
            format=result.format,
        )

    except UnidentifiedImageError as exc:
        result.add_evidence(
            check="pillow",
            passed=False,
            severity="broken",
            message="Pillow no reconoce el archivo como una imagen válida.",
            error=str(exc),
        )
    except (OSError, ValueError, SyntaxError) as exc:
        result.add_evidence(
            check="pillow",
            passed=False,
            severity="broken",
            message="Pillow no pudo verificar o cargar completamente la imagen.",
            error=str(exc),
        )


def validate_with_opencv(path: Path, result: ImageResult) -> None:
    try:
        raw_data = np.fromfile(str(path), dtype=np.uint8)
    except OSError as exc:
        result.add_evidence(
            check="opencv_read",
            passed=False,
            severity="broken",
            message="OpenCV no pudo leer los bytes del archivo.",
            error=str(exc),
        )
        return

    if raw_data.size == 0:
        result.add_evidence(
            check="opencv_read",
            passed=False,
            severity="broken",
            message="El archivo no contiene datos decodificables.",
        )
        return

    decoded = cv2.imdecode(raw_data, cv2.IMREAD_UNCHANGED)

    if decoded is None:
        result.add_evidence(
            check="opencv_decode",
            passed=False,
            severity="broken",
            message="OpenCV no pudo decodificar la imagen.",
        )
        return

    height, width = decoded.shape[:2]

    result.add_evidence(
        check="opencv_decode",
        passed=True,
        severity="info",
        message="OpenCV pudo decodificar la imagen.",
        width=width,
        height=height,
        channels=1 if decoded.ndim == 2 else decoded.shape[2],
    )

    if result.width is not None and result.height is not None:
        if width != result.width or height != result.height:
            result.add_evidence(
                check="decoder_dimensions",
                passed=False,
                severity="review",
                message="Pillow y OpenCV informaron dimensiones diferentes.",
                pillow_width=result.width,
                pillow_height=result.height,
                opencv_width=width,
                opencv_height=height,
            )


def validate_image(path: Path) -> ImageResult:
    result = ImageResult(path=path, status=ImageStatus.OK)

    if not path.exists():
        result.add_evidence(
            check="file_exists",
            passed=False,
            severity="broken",
            message="El archivo no existe.",
        )
        result.status = ImageStatus.BROKEN
        return result

    if not path.is_file():
        result.add_evidence(
            check="is_file",
            passed=False,
            severity="broken",
            message="La ruta no corresponde a un archivo.",
        )
        result.status = ImageStatus.BROKEN
        return result

    try:
        file_size = path.stat().st_size
    except OSError as exc:
        result.add_evidence(
            check="file_size",
            passed=False,
            severity="broken",
            message="No fue posible consultar el tamaño del archivo.",
            error=str(exc),
        )
        result.status = ImageStatus.BROKEN
        return result

    if file_size == 0:
        result.add_evidence(
            check="file_size",
            passed=False,
            severity="broken",
            message="El archivo está vacío.",
        )
        result.status = ImageStatus.BROKEN
        return result

    result.add_evidence(
        check="file_size",
        passed=True,
        severity="info",
        message="El archivo tiene un tamaño válido.",
        bytes=file_size,
    )

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        result.add_evidence(
            check="extension",
            passed=False,
            severity="review",
            message="La extensión no está entre los formatos configurados.",
            extension=extension,
        )

    detected_format = detect_magic_number(path)

    if detected_format is None:
        result.add_evidence(
            check="magic_number",
            passed=False,
            severity="review",
            message="No se reconoció la firma binaria del archivo.",
        )
    else:
        result.add_evidence(
            check="magic_number",
            passed=True,
            severity="info",
            message="Se reconoció la firma binaria del archivo.",
            detected_format=detected_format,
        )

    validate_jpeg_ending(path, result)
    validate_png_ending(path, result)
    validate_with_pillow(path, result)
    validate_with_opencv(path, result)

    return result