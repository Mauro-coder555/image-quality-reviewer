from pathlib import Path

from src.settings import INCLUDE_SUBFOLDERS, KNOWN_IMAGE_EXTENSIONS


def find_image_files(folder_path: Path, include_subfolders: bool = INCLUDE_SUBFOLDERS) -> list[Path]:
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder_path}")

    if not folder_path.is_dir():
        raise NotADirectoryError(f"Path is not a folder: {folder_path}")

    pattern = "**/*" if include_subfolders else "*"
    image_files: list[Path] = []

    for path in folder_path.glob(pattern):
        if path.is_file() and path.suffix.lower() in KNOWN_IMAGE_EXTENSIONS:
            image_files.append(path)

    return sorted(image_files)