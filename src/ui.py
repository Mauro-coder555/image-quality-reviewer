from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.file_actions import move_file_to_trash
from src.image_analysis import ImageAnalysisResult, analyze_image
from src.image_preview import load_preview_image
from src.report import generate_markdown_report
from src.scanner import find_image_files
from src.settings import APP_NAME, INCLUDE_SUBFOLDERS, SHOW_WARNINGS_IN_UI


class ImageQualityReviewerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("1180x720")
        self.root.minsize(1080, 640)

        self.selected_folder: Path | None = None
        self.results: list[ImageAnalysisResult] = []
        self.current_index: int = -1
        self.current_preview_image = None

        self.scan_queue: queue.Queue = queue.Queue()
        self.scan_thread: threading.Thread | None = None
        self.is_scanning = False

        self.total_analyzed = 0
        self.broken_count = 0
        self.suspect_count = 0
        self.review_count = 0

        self.folder_label_var = tk.StringVar(value="No folder selected")
        self.status_var = tk.StringVar(value="Ready")
        self.details_var = tk.StringVar(value="Select an image to preview it.")

        self.create_widgets()
        self.bind_keyboard_shortcuts()

    def run(self) -> None:
        self.root.mainloop()

    def create_widgets(self) -> None:
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X)

        self.select_button = ttk.Button(top_frame, text="Select folder", command=self.select_folder)
        self.select_button.pack(side=tk.LEFT)

        self.scan_button = ttk.Button(top_frame, text="Scan images", command=self.scan_selected_folder)
        self.scan_button.pack(side=tk.LEFT, padx=(8, 0))

        self.report_button = ttk.Button(top_frame, text="Generate report", command=self.generate_report)
        self.report_button.pack(side=tk.LEFT, padx=(8, 0))

        folder_label = ttk.Label(top_frame, textvariable=self.folder_label_var, anchor=tk.W)
        folder_label.pack(side=tk.LEFT, padx=(12, 0), fill=tk.X, expand=True)

        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        columns = ("issue_type", "score", "marked", "dimensions", "blur", "reason")
        self.tree = ttk.Treeview(
            left_frame,
            columns=columns,
            show="tree headings",
            selectmode="extended",
        )

        self.tree.heading("#0", text="File")
        self.tree.heading("issue_type", text="Issue")
        self.tree.heading("score", text="Score")
        self.tree.heading("marked", text="Marked")
        self.tree.heading("dimensions", text="Dimensions")
        self.tree.heading("blur", text="Blur")
        self.tree.heading("reason", text="Reason")

        self.tree.column("#0", width=240)
        self.tree.column("issue_type", width=90, anchor=tk.CENTER)
        self.tree.column("score", width=70, anchor=tk.CENTER)
        self.tree.column("marked", width=80, anchor=tk.CENTER)
        self.tree.column("dimensions", width=100, anchor=tk.CENTER)
        self.tree.column("blur", width=80, anchor=tk.CENTER)
        self.tree.column("reason", width=520)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_selection)

        right_frame = ttk.Frame(content_frame, width=430)
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
            wraplength=430,
            justify=tk.LEFT,
        )
        details_label.pack(fill=tk.X, pady=(8, 0))

        navigation_frame = ttk.Frame(right_frame)
        navigation_frame.pack(fill=tk.X, pady=(10, 0))

        self.previous_button = ttk.Button(navigation_frame, text="Previous", command=self.show_previous_image)
        self.previous_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.next_button = ttk.Button(navigation_frame, text="Next", command=self.show_next_image)
        self.next_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

        actions_frame = ttk.Frame(right_frame)
        actions_frame.pack(fill=tk.X, pady=(10, 0))

        self.mark_button = ttk.Button(actions_frame, text="Mark / unmark", command=self.toggle_mark_current_image)
        self.mark_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.move_current_button = ttk.Button(
            actions_frame,
            text="Move current to trash",
            command=self.move_current_image_to_trash,
        )
        self.move_current_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

        bulk_actions_frame = ttk.Frame(right_frame)
        bulk_actions_frame.pack(fill=tk.X, pady=(8, 0))

        self.move_selected_button = ttk.Button(
            bulk_actions_frame,
            text="Move selected to trash",
            command=self.move_selected_images_to_trash,
        )
        self.move_selected_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.move_marked_button = ttk.Button(
            bulk_actions_frame,
            text="Move marked to trash",
            command=self.move_marked_images_to_trash,
        )
        self.move_marked_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

        status_label = ttk.Label(main_frame, textvariable=self.status_var, anchor=tk.W)
        status_label.pack(fill=tk.X, pady=(8, 0))

    def bind_keyboard_shortcuts(self) -> None:
        self.root.bind("<Right>", lambda event: self.show_next_image())
        self.root.bind("<Left>", lambda event: self.show_previous_image())
        self.root.bind("<space>", lambda event: self.toggle_mark_current_image())

    def select_folder(self) -> None:
        if self.is_scanning:
            messagebox.showinfo("Scan in progress", "Please wait until the current scan finishes.")
            return

        selected_path = filedialog.askdirectory(title="Select image folder")

        if not selected_path:
            return

        self.selected_folder = Path(selected_path)
        self.folder_label_var.set(str(self.selected_folder))
        self.status_var.set("Folder selected. Ready to scan.")

    def scan_selected_folder(self) -> None:
        if self.is_scanning:
            messagebox.showinfo("Scan in progress", "A scan is already running.")
            return

        if self.selected_folder is None:
            messagebox.showwarning("Missing folder", "Please select a folder first.")
            return

        self.clear_results()
        self.reset_scan_counters()
        self.set_scanning_state(True)

        self.status_var.set("Scanning images... The window will remain responsive.")

        self.scan_thread = threading.Thread(
            target=self.scan_worker,
            args=(self.selected_folder,),
            daemon=True,
        )
        self.scan_thread.start()

        self.root.after(100, self.process_scan_queue)

    def scan_worker(self, selected_folder: Path) -> None:
        try:
            image_files = find_image_files(
                selected_folder,
                include_subfolders=INCLUDE_SUBFOLDERS,
            )

            self.scan_queue.put(("total", len(image_files)))

            for image_file in image_files:
                result = analyze_image(image_file)
                self.scan_queue.put(("result", result))

            self.scan_queue.put(("done", None))

        except Exception as error:
            self.scan_queue.put(("error", str(error)))

    def process_scan_queue(self) -> None:
        try:
            while True:
                message_type, payload = self.scan_queue.get_nowait()

                if message_type == "total":
                    total_files = int(payload)
                    self.status_var.set(f"Found {total_files} image-like files. Starting analysis...")

                elif message_type == "result":
                    result = payload
                    self.handle_scan_result(result)

                elif message_type == "done":
                    self.finish_scan()
                    return

                elif message_type == "error":
                    self.finish_scan_with_error(str(payload))
                    return

        except queue.Empty:
            pass

        if self.is_scanning:
            self.root.after(100, self.process_scan_queue)

    def handle_scan_result(self, result: ImageAnalysisResult) -> None:
        self.total_analyzed += 1

        if result.critical_reasons:
            self.broken_count += 1

        if result.suspect_reasons:
            self.suspect_count += 1

        if result.warning_reasons:
            self.review_count += 1

        if self.should_show_result(result):
            self.results.append(result)
            self.insert_result_in_tree(result, len(self.results) - 1)

        if self.total_analyzed % 10 == 0:
            self.update_scan_status()

    def finish_scan(self) -> None:
        self.set_scanning_state(False)
        self.update_scan_status(final=True)

        if self.results:
            self.select_tree_item_by_index(0)
        else:
            self.details_var.set("No broken or suspect images were found.")
            self.preview_label.configure(image="", text="No broken or suspect images found")

    def finish_scan_with_error(self, error_message: str) -> None:
        self.set_scanning_state(False)
        messagebox.showerror("Scan error", error_message)
        self.status_var.set("Scan failed.")

    def update_scan_status(self, final: bool = False) -> None:
        mode_text = "broken and suspect" if not SHOW_WARNINGS_IN_UI else "broken, suspect and review"
        prefix = "Scan completed." if final else "Scanning..."

        self.status_var.set(
            f"{prefix} Files analyzed: {self.total_analyzed}. "
            f"Broken: {self.broken_count}. Suspect: {self.suspect_count}. "
            f"Review: {self.review_count}. Showing: {mode_text}."
        )

    def should_show_result(self, result: ImageAnalysisResult) -> bool:
        if result.critical_reasons:
            return True

        if result.suspect_reasons:
            return True

        if SHOW_WARNINGS_IN_UI and result.warning_reasons:
            return True

        return False

    def reset_scan_counters(self) -> None:
        self.total_analyzed = 0
        self.broken_count = 0
        self.suspect_count = 0
        self.review_count = 0

        while not self.scan_queue.empty():
            try:
                self.scan_queue.get_nowait()
            except queue.Empty:
                break

    def set_scanning_state(self, is_scanning: bool) -> None:
        self.is_scanning = is_scanning
        state = tk.DISABLED if is_scanning else tk.NORMAL

        self.select_button.configure(state=state)
        self.scan_button.configure(state=state)
        self.report_button.configure(state=state)
        self.mark_button.configure(state=state)
        self.move_current_button.configure(state=state)
        self.move_selected_button.configure(state=state)
        self.move_marked_button.configure(state=state)

    def clear_results(self) -> None:
        self.results = []
        self.current_index = -1
        self.current_preview_image = None
        self.tree.delete(*self.tree.get_children())
        self.preview_label.configure(image="", text="Preview not available")
        self.details_var.set("Select an image to preview it.")

    def populate_results_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())

        for index, result in enumerate(self.results):
            self.insert_result_in_tree(result, index)

    def insert_result_in_tree(self, result: ImageAnalysisResult, index: int) -> None:
        self.tree.insert(
            "",
            tk.END,
            iid=str(index),
            text=result.path.name,
            values=(
                result.issue_type,
                result.score,
                "Yes" if result.marked_for_deletion else "No",
                self.format_dimensions(result),
                self.format_blur_score(result),
                self.format_reason_summary(result),
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
            self.preview_label.configure(image="", text="Preview not available")
        else:
            self.current_preview_image = preview_image
            self.preview_label.configure(image=self.current_preview_image, text="")

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
        if self.is_scanning:
            return

        if self.current_index < 0 or self.current_index >= len(self.results):
            return

        result = self.results[self.current_index]
        result.marked_for_deletion = not result.marked_for_deletion

        self.populate_results_tree()
        self.select_tree_item_by_index(self.current_index)

    def move_current_image_to_trash(self) -> None:
        if self.is_scanning:
            return

        if self.current_index < 0 or self.current_index >= len(self.results):
            return

        result = self.results[self.current_index]
        self.move_results_to_trash([result])

    def move_selected_images_to_trash(self) -> None:
        if self.is_scanning:
            return

        selected_items = self.tree.selection()

        if not selected_items:
            messagebox.showinfo("No selection", "Please select at least one image.")
            return

        selected_results = [self.results[int(item)] for item in selected_items]
        self.move_results_to_trash(selected_results)

    def move_marked_images_to_trash(self) -> None:
        if self.is_scanning:
            return

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
                result.critical_reasons.append(f"Move to trash failed: {error}")
                failed_count += 1

        self.results = [
            result for result in self.results if result.status != "moved to trash"
        ]

        self.rebuild_tree_after_file_actions()

        self.status_var.set(
            f"Move completed. Moved: {moved_count}. Failed: {failed_count}."
        )

    def rebuild_tree_after_file_actions(self) -> None:
        self.populate_results_tree()

        if self.results:
            self.select_tree_item_by_index(0)
        else:
            self.current_index = -1
            self.current_preview_image = None
            self.preview_label.configure(image="", text="No remaining listed images")
            self.details_var.set("No remaining listed images.")

    def generate_report(self) -> None:
        if self.is_scanning:
            messagebox.showinfo("Scan in progress", "Please wait until the current scan finishes.")
            return

        if self.selected_folder is None:
            messagebox.showwarning("Missing folder", "Please select a folder first.")
            return

        if not self.results:
            confirmed = messagebox.askyesno(
                "Generate report",
                "There are no current listed images. Generate report anyway?",
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
            f"Issue: {result.issue_type}",
            f"Status: {result.status}",
            f"Score: {result.score}",
            f"Dimensions: {self.format_dimensions(result)}",
            f"Blur score: {self.format_blur_score(result)}",
            f"Marked for deletion: {'Yes' if result.marked_for_deletion else 'No'}",
            "",
            "Broken reasons:",
            self.format_reason_list(result.critical_reasons),
            "",
            "Suspect reasons:",
            self.format_reason_list(result.suspect_reasons),
            "",
            "Review notes:",
            self.format_reason_list(result.warning_reasons),
            "",
            "Info:",
            self.format_reason_list(result.info_reasons),
        ]

        return "\n".join(details)

    @staticmethod
    def format_reason_summary(result: ImageAnalysisResult) -> str:
        if result.critical_reasons:
            return "; ".join(result.critical_reasons)

        if result.suspect_reasons:
            return "; ".join(result.suspect_reasons)

        if result.warning_reasons:
            return "; ".join(result.warning_reasons)

        if result.info_reasons:
            return "; ".join(result.info_reasons)

        return "No issues"

    @staticmethod
    def format_reason_list(reasons: list[str]) -> str:
        if not reasons:
            return "- None"

        return "\n".join(f"- {reason}" for reason in reasons)

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