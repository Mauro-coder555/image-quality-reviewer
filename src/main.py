import tkinter as tk

from src.gui import ImageReviewApp


def main() -> None:
    root = tk.Tk()
    ImageReviewApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()