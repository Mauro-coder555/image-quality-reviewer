from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk, UnidentifiedImageError
from send2trash import send2trash

from src.processor import find_images, process_image
from src.models import ImageResult, ImageStatus


PREVIEW_SIZE = (700, 650)


class ImageReviewApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Image Quality Reviewer")
        self.root.geometry("1200x760")
        self.root.minsize(900, 600)

        self.folder: Path | None = None
        self.results: list[ImageResult] = []
        self.filtered_results: list[ImageResult] = []

        self.selected_result: ImageResult | None = None
        self.preview_image: ImageTk.PhotoImage | None = None

        self.scan_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.scan_running = False

        self.filter_var = tk.StringVar(value="Todos")
        self.folder_var = tk.StringVar(value="Ninguna carpeta seleccionada")
        self.status_var = tk.StringVar(value="Selecciona una carpeta para comenzar.")

        self.create_widgets()
        self.root.after(100, self.process_scan_queue)

    def create_widgets(self) -> None:
        toolbar = ttk.Frame(self.root, padding=10)
        toolbar.pack(fill=tk.X)

        ttk.Button(
            toolbar,
            text="Seleccionar carpeta",
            command=self.select_folder,
        ).pack(side=tk.LEFT)

        self.scan_button = ttk.Button(
            toolbar,
            text="Analizar",
            command=self.start_scan,
            state=tk.DISABLED,
        )
        self.scan_button.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(
            toolbar,
            text="Filtro:",
        ).pack(side=tk.LEFT, padx=(24, 5))

        filter_box = ttk.Combobox(
            toolbar,
            textvariable=self.filter_var,
            values=["Todos", "OK", "Review", "Broken"],
            state="readonly",
            width=12,
        )
        filter_box.pack(side=tk.LEFT)
        filter_box.bind("<<ComboboxSelected>>", self.apply_filter)

        ttk.Label(
            toolbar,
            textvariable=self.folder_var,
        ).pack(side=tk.LEFT, padx=(24, 0), fill=tk.X, expand=True)

        self.progress = ttk.Progressbar(
            self.root,
            mode="determinate",
        )
        self.progress.pack(fill=tk.X, padx=10)

        main_pane = ttk.PanedWindow(
            self.root,
            orient=tk.HORIZONTAL,
        )
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        list_frame = ttk.Frame(main_pane)
        preview_frame = ttk.Frame(main_pane)

        main_pane.add(list_frame, weight=2)
        main_pane.add(preview_frame, weight=3)

        self.create_result_table(list_frame)
        self.create_preview_panel(preview_frame)

        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            anchor=tk.W,
            padding=(10, 5),
        )
        status_bar.pack(fill=tk.X)

    def create_result_table(self, parent: ttk.Frame) -> None:
        columns = ("status", "name", "format", "dimensions")

        self.tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        self.tree.heading("status", text="Estado")
        self.tree.heading("name", text="Archivo")
        self.tree.heading("format", text="Formato")
        self.tree.heading("dimensions", text="Dimensiones")

        self.tree.column("status", width=80, anchor=tk.CENTER)
        self.tree.column("name", width=330)
        self.tree.column("format", width=80, anchor=tk.CENTER)
        self.tree.column("dimensions", width=110, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(
            parent,
            orient=tk.VERTICAL,
            command=self.tree.yview,
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self.on_image_selected)
        self.tree.bind("<Double-1>", lambda _: self.open_selected_image())

        self.tree.tag_configure("broken", background="#ffd6d6")
        self.tree.tag_configure("review", background="#fff1bf")
        self.tree.tag_configure("ok", background="#dff5df")

    def create_preview_panel(self, parent: ttk.Frame) -> None:
        self.preview_label = ttk.Label(
            parent,
            text="Selecciona una imagen",
            anchor=tk.CENTER,
        )
        self.preview_label.pack(fill=tk.BOTH, expand=True)

        info_frame = ttk.Frame(parent, padding=(0, 10))
        info_frame.pack(fill=tk.X)

        self.info_var = tk.StringVar(value="")
        ttk.Label(
            info_frame,
            textvariable=self.info_var,
            justify=tk.LEFT,
        ).pack(fill=tk.X)

        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(0, 5))

        self.open_button = ttk.Button(
            button_frame,
            text="Abrir imagen",
            command=self.open_selected_image,
            state=tk.DISABLED,
        )
        self.open_button.pack(side=tk.LEFT)

        self.delete_button = ttk.Button(
            button_frame,
            text="Enviar a la Papelera",
            command=self.delete_selected_image,
            state=tk.DISABLED,
        )
        self.delete_button.pack(side=tk.LEFT, padx=(8, 0))

    def select_folder(self) -> None:
        selected = filedialog.askdirectory(
            title="Selecciona la carpeta de imágenes"
        )

        if not selected:
            return

        self.folder = Path(selected)
        self.folder_var.set(str(self.folder))
        self.scan_button.configure(state=tk.NORMAL)

        self.results.clear()
        self.filtered_results.clear()
        self.clear_table()
        self.clear_preview()

        self.status_var.set(
            "Carpeta seleccionada. Presiona Analizar para comenzar."
        )

    def start_scan(self) -> None:
        if self.folder is None or self.scan_running:
            return

        self.scan_running = True
        self.scan_button.configure(state=tk.DISABLED)
        self.results.clear()
        self.filtered_results.clear()
        self.clear_table()
        self.clear_preview()

        images = find_images(self.folder)

        if not images:
            self.scan_running = False
            self.scan_button.configure(state=tk.NORMAL)
            self.status_var.set("No se encontraron imágenes compatibles.")
            messagebox.showinfo(
                "Sin imágenes",
                "No se encontraron imágenes compatibles en la carpeta.",
            )
            return

        self.progress.configure(
            maximum=len(images),
            value=0,
        )

        self.status_var.set(
            f"Analizando {len(images)} imágenes..."
        )

        worker = threading.Thread(
            target=self.scan_images,
            args=(images,),
            daemon=True,
        )
        worker.start()

    def scan_images(self, images: list[Path]) -> None:
        for index, image_path in enumerate(images, start=1):
            try:
                result = process_image(image_path)
                self.scan_queue.put(("result", result))
            except Exception as exc:
                self.scan_queue.put(
                    (
                        "error",
                        (image_path, str(exc)),
                    )
                )

            self.scan_queue.put(
                (
                    "progress",
                    (index, len(images)),
                )
            )

        self.scan_queue.put(("finished", None))

    def process_scan_queue(self) -> None:
        try:
            while True:
                event, data = self.scan_queue.get_nowait()

                if event == "result":
                    result = data

                    if isinstance(result, ImageResult):
                        self.results.append(result)

                        if self.result_matches_filter(result):
                            self.insert_result(result)

                elif event == "error":
                    image_path, error = data
                    self.status_var.set(
                        f"Error procesando {image_path}: {error}"
                    )

                elif event == "progress":
                    current, total = data
                    self.progress.configure(value=current)
                    self.status_var.set(
                        f"Analizando imagen {current} de {total}..."
                    )

                elif event == "finished":
                    self.finish_scan()

        except queue.Empty:
            pass

        self.root.after(100, self.process_scan_queue)

    def finish_scan(self) -> None:
        self.scan_running = False
        self.scan_button.configure(state=tk.NORMAL)

        counts = {
            ImageStatus.OK: 0,
            ImageStatus.REVIEW: 0,
            ImageStatus.BROKEN: 0,
        }

        for result in self.results:
            counts[result.status] += 1

        self.status_var.set(
            f"Análisis completado. "
            f"OK: {counts[ImageStatus.OK]} | "
            f"Review: {counts[ImageStatus.REVIEW]} | "
            f"Broken: {counts[ImageStatus.BROKEN]}"
        )

    def apply_filter(self, _event: object | None = None) -> None:
        self.clear_table()
        self.clear_preview()

        for result in self.results:
            if self.result_matches_filter(result):
                self.insert_result(result)

        visible = len(self.tree.get_children())

        self.status_var.set(
            f"Mostrando {visible} de {len(self.results)} imágenes."
        )

    def result_matches_filter(self, result: ImageResult) -> bool:
        selected_filter = self.filter_var.get()

        if selected_filter == "Todos":
            return True

        return result.status.value == selected_filter

    def insert_result(self, result: ImageResult) -> None:
        dimensions = "-"

        if result.width is not None and result.height is not None:
            dimensions = f"{result.width} × {result.height}"

        tag = result.status.value.lower()

        self.tree.insert(
            "",
            tk.END,
            iid=str(result.path),
            values=(
                result.status.value,
                result.path.name,
                result.format or "-",
                dimensions,
            ),
            tags=(tag,),
        )

    def on_image_selected(self, _event: object | None = None) -> None:
        selected_items = self.tree.selection()

        if not selected_items:
            self.clear_preview()
            return

        selected_path = Path(selected_items[0])

        self.selected_result = next(
            (
                result
                for result in self.results
                if result.path == selected_path
            ),
            None,
        )

        if self.selected_result is None:
            self.clear_preview()
            return

        self.show_preview(self.selected_result)

    def show_preview(self, result: ImageResult) -> None:
        self.open_button.configure(state=tk.NORMAL)
        self.delete_button.configure(state=tk.NORMAL)

        failed_evidence = [
            evidence.message
            for evidence in result.evidence
            if not evidence.passed
        ]

        evidence_text = "\n".join(
            f"• {message}"
            for message in failed_evidence
        )

        if not evidence_text:
            evidence_text = "No se encontraron problemas."

        self.info_var.set(
            f"Archivo: {result.path.name}\n"
            f"Estado: {result.status.value}\n"
            f"Formato: {result.format or 'Desconocido'}\n"
            f"Ruta: {result.path}\n\n"
            f"Evidencias:\n{evidence_text}"
        )

        try:
            with Image.open(result.path) as image:
                preview = image.copy()
                preview.thumbnail(PREVIEW_SIZE)

            self.preview_image = ImageTk.PhotoImage(preview)

            self.preview_label.configure(
                image=self.preview_image,
                text="",
            )

        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
        ):
            self.preview_image = None
            self.preview_label.configure(
                image="",
                text=(
                    "No se puede generar una vista previa.\n\n"
                    "El archivo podría estar corrupto."
                ),
            )

    def open_selected_image(self) -> None:
        if self.selected_result is None:
            return

        path = self.selected_result.path

        if not path.exists():
            messagebox.showerror(
                "Archivo no encontrado",
                "El archivo ya no existe.",
            )
            self.remove_result_from_interface(path)
            return

        try:
            os.startfile(path)
        except OSError as exc:
            messagebox.showerror(
                "No se pudo abrir",
                f"No se pudo abrir la imagen:\n\n{exc}",
            )

    def delete_selected_image(self) -> None:
        if self.selected_result is None:
            return

        result = self.selected_result
        path = result.path

        confirmed = messagebox.askyesno(
            "Enviar a la Papelera",
            (
                "La imagen se enviará a la Papelera de reciclaje.\n\n"
                f"Archivo: {path.name}\n"
                f"Estado: {result.status.value}\n\n"
                "¿Deseas continuar?"
            ),
            icon=messagebox.WARNING,
        )

        if not confirmed:
            return

        try:
            send2trash(str(path))
        except OSError as exc:
            messagebox.showerror(
                "No se pudo eliminar",
                f"No se pudo enviar el archivo a la Papelera:\n\n{exc}",
            )
            return

        self.remove_result_from_interface(path)

        self.status_var.set(
            f"Archivo enviado a la Papelera: {path.name}"
        )

    def remove_result_from_interface(self, path: Path) -> None:
        self.results = [
            result
            for result in self.results
            if result.path != path
        ]

        item_id = str(path)

        if self.tree.exists(item_id):
            self.tree.delete(item_id)

        self.clear_preview()

    def clear_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

    def clear_preview(self) -> None:
        self.selected_result = None
        self.preview_image = None

        self.preview_label.configure(
            image="",
            text="Selecciona una imagen",
        )

        self.info_var.set("")
        self.open_button.configure(state=tk.DISABLED)
        self.delete_button.configure(state=tk.DISABLED)