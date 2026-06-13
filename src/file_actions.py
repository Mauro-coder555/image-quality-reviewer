import shutil
from pathlib import Path

from src.settings import TRASH_DIR


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def move_file_to_trash(file_path: Path, trash_dir: Path = TRASH_DIR) -> Path:
    if not file_path.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")

    ensure_directory(trash_dir)

    destination_path = build_safe_destination_path(file_path, trash_dir)
    shutil.move(str(file_path), str(destination_path))

    return destination_path


def delete_file_permanently(file_path: Path) -> None:
    if not file_path.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")

    file_path.unlink()


def build_safe_destination_path(file_path: Path, trash_dir: Path) -> Path:
    destination_path = trash_dir / file_path.name

    if not destination_path.exists():
        return destination_path

    stem = file_path.stem
    suffix = file_path.suffix

    counter = 1
    while True:
        candidate_path = trash_dir / f"{stem}_{counter}{suffix}"

        if not candidate_path.exists():
            return candidate_path

        counter += 1