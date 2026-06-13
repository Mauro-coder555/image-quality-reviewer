from pathlib import Path
from tkinter import Tk

from PIL import Image, ImageTk, UnidentifiedImageError


def load_preview_image(
    root: Tk,
    image_path: Path,
    max_width: int = 520,
    max_height: int = 420,
) -> ImageTk.PhotoImage | None:
    try:
        with Image.open(image_path) as image:
            image.load()
            image.thumbnail((max_width, max_height))
            preview_image = image.copy()

        return ImageTk.PhotoImage(preview_image, master=root)

    except (UnidentifiedImageError, OSError):
        return None