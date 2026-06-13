from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.file_actions import move_file_to_trash
from src.image_analysis import ImageAnalysisResult, analyze_image
from src.image_preview import load_preview_image
from src.report import generate_markdown_report
from src.scanner import find_image_files
from src.settings import APP_NAME, INCLUDE_SUBFOLDERS


class ImageQualityReviewerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("1100x700")
        self.root.minsize(1000, 620)

        self.selected_folder: Path | None = None
        self.results: list[ImageAnalysisResult] = []
        self.current_index: int = -1
        self.current_preview_image = None

        self.folder_label_var = tk.StringVar(value="No folder selected")
        self.status_var = tk.StringVar(value="Ready")
        self.details_var = tk.StringVar(value="Select a problematic image to preview it.")

        self.create_widgets()
        self.bind_keyboard_shortcuts()

    def run(self) -> None:
        self.root.mainloop()

    def create_widgets(self) -> None:
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X)

        select_button = ttk.Button(
            top_frame,
            text="Select folder",
            command=self.select_folder,
        )
        select_button.pack(side=tk.LEFT)

        scan_button = ttk.Button(
            top_frame,
            text="Scan images",
            command=self.scan_selected_folder,
        )
        scan_button.pack(side=tk.LEFT, padx=(8, 0))

        report_button = ttk.Button(
            top_frame,
            text="Generate report",
            command=self.generate_report,
        )
        report_button.pack(side=tk.LEFT, padx=(8, 0))

        folder_label = ttk.Label(
            top_frame,
            textvariable=self.folder_label_var,
            anchor=tk.W,
        )
        folder_label.pack(side=tk.LEFT, padx=(12, 0), fill=tk.X, expand=True)

        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        columns = ("status", "marked", "dimensions", "blur", "reason")
        self.tree = ttk.Treeview(
            left_frame,
            columns=columns,
            show="tree headings",
            selectmode="extended",
        )

        self.tree.heading("#0", text="File")
        self.tree.heading("status", text="Status")
        self.tree.heading("marked", text="Marked")
        self.tree.heading("dimensions", text="Dimensions")
        self.tree.heading("blur", text="Blur")
        self.tree.heading("reason", text="Reason")

        self.tree.column("#0", width=280)
        self.tree.column("status", width=120)
        self.tree.column("marked", width=80, anchor=tk.CENTER)
        self.tree.column("dimensions", width=100, anchor=tk.CENTER)
        self.tree.column("blur", width=80, anchor=tk.CENTER)
        self.tree.column("reason", width=360)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_selection)

        right_frame = ttk.Frame(content_frame, width=420)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(12, 0))

        self.preview_label = ttk.Label(
            right_frame,
            text="Preview not available",
            anchor=tk.CENTER,
            relief=tk.SUNKEN,
        )
        self.preview_label.pack(fill=tk.BOTH, expand=True)

        details_label = ttk.Label(
            right_frame,
            textvariable=self.details_var,
            wraplength=420,
            justify=tk.LEFT,
        )
        details_label.pack(fill=tk.X, pady=(8, 0))

        navigation_frame = ttk.Frame(right_frame)
        navigation_frame.pack(fill=tk.X, pady=(10, 0))

        previous_button = ttk.Button(
            navigation_frame,
            text="Previous",
            command=self.show_previous_image,
        )
        previous_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

        next_button = ttk.Button(
            navigation_frame,
            text="Next",
            command=self.show_next_image,
        )
        next_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

        actions_frame = ttk.Frame(right_frame)
        actions_frame.pack(fill=tk.X, pady=(10, 0))

        mark_button = ttk.Button(
            actions_frame,
            text="Mark / unmark",
            command=self.toggle_mark_current_image,
        )
        mark_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

        move_current_button = ttk.Button(
            actions_frame,
            text="Move current to trash",
            command=self.move_current_image_to_trash,
        )
        move_current_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

        bulk_actions_frame = ttk.Frame(right_frame)
        bulk_actions_frame.pack(fill=tk.X, pady=(8, 0))

        move_selected_button = ttk.Button(
            bulk_actions_frame,
            text="Move selected to trash",
            command=self.move_selected_images_to_trash,
        )
        move_selected_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

        move_marked_button = ttk.Button(
            bulk_actions_frame,
            text="Move marked to trash",
            command=self.move_marked_images_to_trash,
        )
        move_marked_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

        status_label = ttk.Label(
            main_frame,
            textvariable=self.status_var,
            anchor=tk.W,
        )
        status_label.pack(fill=tk.X, pady=(8, 0))

    def bind_keyboard_shortcuts(self) -> None:
        self.root.bind("<Right>", lambda event: self.show_next_image())
        self.root.bind("<Left>", lambda event: self.show_previous_image())
        self.root.bind("<space>", lambda event: self.toggle_mark_current_image())

    def select_folder(self) -> None:
        selected_path = filedialog.askdirectory(title="Select image folder")

        if not selected_path:
            return

        self.selected_folder = Path(selected_path)
        self.folder_label_var.set(str(self.selected_folder))
        self.status_var.set("Folder selected. Ready to scan.")

    def scan_selected_folder(self) -> None:
        if self.selected_folder is None:
            messagebox.showwarning("Missing folder", "Please select a folder first.")
            return

        self.clear_results()
        self.status_var.set("Scanning images...")
        self.root.update_idletasks()

        try:
            image_files = find_image_files(
                self.selected_folder,
                include_subfolders=INCLUDE_SUBFOLDERS,
            )

            for image_file in image_files:
                result = analyze_image(image_file)

                if result.is_problematic:
                    self.results.append(result)

            self.populate_results_tree()

            self.status_var.set(
                f"Scan completed. Problematic images found: {len(self.results)}"
            )

            if self.results:
                self.select_tree_item_by_index(0)
            else:
                self.details_var.set("No problematic images were found.")
                self.preview_label.configure(image="", text="No problematic images found")

        except Exception as error:
            messagebox.showerror("Scan error", str(error))
            self.status_var.set("Scan failed.")

    def clear_results(self) -> None:
        self.results = []
        self.current_index = -1
        self.current_preview_image = None
        self.tree.delete(*self.tree.get_children())
        self.preview_label.configure(image="", text="Preview not available")
        self.details_var.set("Select a problematic image to preview it.")

    def populate_results_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())

        for index, result in enumerate(self.results):
            self.tree.insert(
                "",
                tk.END,
                iid=str(index),
                text=result.path.name,
                values=(
                    result.status,
                    "Yes" if result.marked_for_deletion else "No",
                    self.format_dimensions(result),
                    self.format_blur_score(result),
                    "; ".join(result.reasons),
                ),
            )

    def on_tree_selection(self, event: object) -> None:
        selected_items = self.tree.selection()

        if not selected_items:
            return

        first_selected_item = selected_items[0]
        self.current_index = int(first_selected_item)
        self.show_current_image()

    def show_current_image(self) -> None:
        if self.current_index < 0 or self.current_index >= len(self.results):
            return

        result = self.results[self.current_index]
        preview_image = load_preview_image(self.root, result.path)

        if preview_image is None:
            self.current_preview_image = None
            self.preview_label.configure(
                image="",
                text="Preview not available",
            )
        else:
            self.current_preview_image = preview_image
            self.preview_label.configure(
                image=self.current_preview_image,
                text="",
            )

        self.details_var.set(self.build_details_text(result))

    def show_next_image(self) -> None:
        if not self.results:
            return

        next_index = min(self.current_index + 1, len(self.results) - 1)
        self.select_tree_item_by_index(next_index)

    def show_previous_image(self) -> None:
        if not self.results:
            return

        previous_index = max(self.current_index - 1, 0)
        self.select_tree_item_by_index(previous_index)

    def select_tree_item_by_index(self, index: int) -> None:
        if index < 0 or index >= len(self.results):
            return

        item_id = str(index)
        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        self.tree.see(item_id)

        self.current_index = index
        self.show_current_image()

    def toggle_mark_current_image(self) -> None:
        if self.current_index < 0 or self.current_index >= len(self.results):
            return

        result = self.results[self.current_index]
        result.marked_for_deletion = not result.marked_for_deletion

        self.populate_results_tree()
        self.select_tree_item_by_index(self.current_index)

    def move_current_image_to_trash(self) -> None:
        if self.current_index < 0 or self.current_index >= len(self.results):
            return

        result = self.results[self.current_index]
        self.move_results_to_trash([result])

    def move_selected_images_to_trash(self) -> None:
        selected_items = self.tree.selection()

        if not selected_items:
            messagebox.showinfo("No selection", "Please select at least one image.")
            return

        selected_results = [self.results[int(item)] for item in selected_items]
        self.move_results_to_trash(selected_results)

    def move_marked_images_to_trash(self) -> None:
        marked_results = [
            result for result in self.results if result.marked_for_deletion
        ]

        if not marked_results:
            messagebox.showinfo("No marked images", "No images are marked for deletion.")
            return

        self.move_results_to_trash(marked_results)

    def move_results_to_trash(self, results_to_move: list[ImageAnalysisResult]) -> None:
        if not results_to_move:
            return

        confirmation_message = (
            f"You are about to move {len(results_to_move)} file(s) to the local trash folder.\n\n"
            "This will not permanently delete them, but they will be moved from their original location.\n\n"
            "Do you want to continue?"
        )

        confirmed = messagebox.askyesno("Confirm move to trash", confirmation_message)

        if not confirmed:
            return

        moved_count = 0
        failed_count = 0

        for result in results_to_move:
            try:
                move_file_to_trash(result.path)
                result.status = "moved to trash"
                moved_count += 1

            except Exception as error:
                result.status = "move failed"
                result.reasons.append(f"Move to trash failed: {error}")
                failed_count += 1

        self.results = [
            result for result in self.results if result.status != "moved to trash"
        ]

        self.populate_results_tree()

        if self.results:
            self.select_tree_item_by_index(0)
        else:
            self.current_index = -1
            self.current_preview_image = None
            self.preview_label.configure(image="", text="No remaining problematic images")
            self.details_var.set("No remaining problematic images.")

        self.status_var.set(
            f"Move completed. Moved: {moved_count}. Failed: {failed_count}."
        )

    def generate_report(self) -> None:
        if self.selected_folder is None:
            messagebox.showwarning("Missing folder", "Please select a folder first.")
            return

        if not self.results:
            confirmed = messagebox.askyesno(
                "Generate report",
                "There are no current problematic images listed. Generate report anyway?",
            )

            if not confirmed:
                return

        try:
            report_path = generate_markdown_report(self.selected_folder, self.results)
            messagebox.showinfo("Report generated", f"Report saved at:\n{report_path}")
            self.status_var.set(f"Report generated: {report_path}")

        except Exception as error:
            messagebox.showerror("Report error", str(error))
            self.status_var.set("Report generation failed.")

    def build_details_text(self, result: ImageAnalysisResult) -> str:
        details = [
            f"File: {result.path.name}",
            f"Path: {result.path}",
            f"Status: {result.status}",
            f"Dimensions: {self.format_dimensions(result)}",
            f"Blur score: {self.format_blur_score(result)}",
            f"Marked for deletion: {'Yes' if result.marked_for_deletion else 'No'}",
            f"Reasons: {'; '.join(result.reasons)}",
        ]

        return "\n".join(details)

    @staticmethod
    def format_dimensions(result: ImageAnalysisResult) -> str:
        if result.width is None or result.height is None:
            return "not available"

        return f"{result.width}x{result.height}"

    @staticmethod
    def format_blur_score(result: ImageAnalysisResult) -> str:
        if result.blur_score is None:
            return "not available"

        return f"{result.blur_score:.2f}"