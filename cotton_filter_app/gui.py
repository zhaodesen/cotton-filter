"""Tkinter GUI for cotton-filter."""

from __future__ import annotations

import threading
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Iterable

from .constants import APP_NAME
from .file_utils import (
    default_output_dir,
    expand_targets,
    filter_files,
    open_folder,
)
from .models import FileResult


class CottonFilterApp:
    """cotton-filter 的 Tkinter 图形界面。"""

    COLORS = {
        "window": "#f5f6f4",
        "panel": "#ffffff",
        "border": "#d8ddd8",
        "text": "#1d2320",
        "muted": "#66706a",
        "soft": "#eef2ef",
        "accent": "#166c5f",
        "accent_bg": "#e5f2ef",
        "danger": "#b42318",
        "success": "#087443",
    }

    def __init__(self, root: Any) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.root = root
        self.files: list[Path] = []
        self.output_dir: Path | None = None
        self.log_queue: Queue[str] = Queue()
        self.result_queue: Queue[list[FileResult]] = Queue()
        self.processing_active = False

        self.status_var = tk.StringVar(value="请选择 Excel 文件或文件夹")
        self.output_var = tk.StringVar(value="未选择保存目录")
        self.count_var = tk.StringVar(value="0 个文件")

        self.add_files_btn: Any = None
        self.clear_btn: Any = None
        self.output_btn: Any = None
        self.run_btn: Any = None
        self.clear_log_btn: Any = None
        self.open_dir_btn: Any = None
        self.file_list: Any = None
        self.log: Any = None

        self.configure_root()
        self.configure_styles()
        self.build_layout()

    def configure_root(self) -> None:
        """设置主窗口。"""

        self.root.title(APP_NAME)
        self.root.geometry("920x640")
        self.root.minsize(820, 560)
        self.root.configure(bg=self.COLORS["window"])

    def configure_styles(self) -> None:
        """设置 ttk 风格。"""

        style = self.ttk.Style(self.root)
        try:
            style.theme_use("aqua")
        except self.tk.TclError:
            try:
                style.theme_use("clam")
            except self.tk.TclError:
                pass

        style.configure("App.TFrame", background=self.COLORS["window"])
        style.configure("Panel.TFrame", background=self.COLORS["panel"])
        style.configure(
            "Title.TLabel",
            background=self.COLORS["window"],
            foreground=self.COLORS["text"],
            font=("Arial", 22, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=self.COLORS["window"],
            foreground=self.COLORS["muted"],
            font=("Arial", 12),
        )
        style.configure(
            "Section.TLabel",
            background=self.COLORS["panel"],
            foreground=self.COLORS["text"],
            font=("Arial", 12, "bold"),
        )
        style.configure(
            "Hint.TLabel",
            background=self.COLORS["panel"],
            foreground=self.COLORS["muted"],
            font=("Arial", 11),
        )
        style.configure(
            "Status.TLabel",
            background=self.COLORS["window"],
            foreground=self.COLORS["muted"],
            font=("Arial", 11),
        )
        style.configure("Primary.TButton", padding=(14, 7))
        style.configure("TButton", padding=(11, 6))
        style.configure(
            "Files.Treeview",
            background=self.COLORS["panel"],
            fieldbackground=self.COLORS["panel"],
            foreground=self.COLORS["text"],
            rowheight=28,
            borderwidth=0,
            font=("Arial", 11),
        )
        style.configure(
            "Files.Treeview.Heading",
            background=self.COLORS["soft"],
            foreground=self.COLORS["muted"],
            font=("Arial", 11, "bold"),
        )
        style.map(
            "Files.Treeview",
            background=[("selected", self.COLORS["accent_bg"])],
            foreground=[("selected", self.COLORS["text"])],
        )

    def build_layout(self) -> None:
        """构建主界面。"""

        frame = self.ttk.Frame(self.root, padding=(24, 20), style="App.TFrame")
        frame.pack(fill=self.tk.BOTH, expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)

        self.build_header(frame)
        self.build_actions(frame)
        self.build_summary(frame)
        self.build_body(frame)
        self.build_footer(frame)

    def build_header(self, parent: Any) -> None:
        """构建标题区。"""

        header = self.ttk.Frame(parent, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        self.ttk.Label(header, text=APP_NAME, style="Title.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.ttk.Label(
            header,
            text="Excel 筛选工具",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

    def build_actions(self, parent: Any) -> None:
        """构建操作区。"""

        actions = self.ttk.Frame(parent, style="App.TFrame")
        actions.grid(row=1, column=0, sticky="ew", pady=(18, 12))
        actions.columnconfigure(4, weight=1)

        self.add_files_btn = self.ttk.Button(
            actions,
            text="添加 Excel",
            command=self.add_files,
        )
        self.add_files_btn.grid(row=0, column=0, padx=(0, 8))

        self.output_btn = self.ttk.Button(
            actions,
            text="选择保存目录",
            command=self.choose_output_dir,
        )
        self.output_btn.grid(row=0, column=1, padx=(0, 8))

        self.clear_btn = self.ttk.Button(
            actions,
            text="清空",
            command=self.clear_files,
        )
        self.clear_btn.grid(row=0, column=2, padx=(0, 14))

        self.run_btn = self.ttk.Button(
            actions,
            text="开始筛选",
            command=self.start_processing,
            style="Primary.TButton",
        )
        self.run_btn.grid(row=0, column=3, padx=(0, 8))

    def build_summary(self, parent: Any) -> None:
        """构建摘要栏。"""

        summary = self.ttk.Frame(parent, padding=(14, 10), style="Panel.TFrame")
        summary.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        summary.columnconfigure(1, weight=1)

        self.ttk.Label(
            summary,
            textvariable=self.count_var,
            style="Section.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=(0, 18))
        self.ttk.Label(
            summary,
            textvariable=self.output_var,
            style="Hint.TLabel",
        ).grid(row=0, column=1, sticky="ew")

    def build_body(self, parent: Any) -> None:
        """构建主工作区。"""

        body = self.ttk.PanedWindow(parent, orient=self.tk.VERTICAL)
        body.grid(row=3, column=0, sticky="nsew")

        body.add(self.build_files_box(body), weight=2)
        body.add(self.build_log_box(body), weight=3)

    def build_files_box(self, parent: Any) -> Any:
        """构建文件表格。"""

        box = self.create_panel(parent)
        box.columnconfigure(0, weight=1)
        box.rowconfigure(1, weight=1)

        header = self.ttk.Frame(box, style="Panel.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        header.columnconfigure(1, weight=1)

        self.ttk.Label(header, text="待处理文件", style="Section.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.ttk.Label(
            header,
            text="支持 .xlsx / .xls",
            style="Hint.TLabel",
        ).grid(row=0, column=1, sticky="e")

        self.file_list = self.ttk.Treeview(
            box,
            columns=("name", "folder"),
            show="headings",
            height=7,
            style="Files.Treeview",
        )
        self.file_list.heading("name", text="文件名")
        self.file_list.heading("folder", text="位置")
        self.file_list.column("name", width=320, minwidth=180, anchor="w")
        self.file_list.column("folder", width=480, minwidth=240, anchor="w")
        self.file_list.grid(row=1, column=0, sticky="nsew")

        scroll = self.ttk.Scrollbar(
            box,
            orient=self.tk.VERTICAL,
            command=self.file_list.yview,
        )
        scroll.grid(row=1, column=1, sticky="ns")
        self.file_list.configure(yscrollcommand=scroll.set)

        return box

    def build_log_box(self, parent: Any) -> Any:
        """构建日志区。"""

        box = self.create_panel(parent)
        box.columnconfigure(0, weight=1)
        box.rowconfigure(1, weight=1)

        header = self.ttk.Frame(box, style="Panel.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        header.columnconfigure(1, weight=1)

        self.ttk.Label(header, text="处理日志", style="Section.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.clear_log_btn = self.ttk.Button(
            header,
            text="清空日志",
            command=self.clear_log,
        )
        self.clear_log_btn.grid(row=0, column=1, sticky="e")

        self.log = self.tk.Text(
            box,
            height=10,
            wrap="word",
            state="disabled",
            bg=self.COLORS["panel"],
            fg=self.COLORS["text"],
            relief=self.tk.FLAT,
            bd=0,
            padx=10,
            pady=8,
            font=("Menlo", 11),
            highlightthickness=1,
            highlightbackground=self.COLORS["border"],
            highlightcolor=self.COLORS["border"],
        )
        self.log.tag_configure("success", foreground=self.COLORS["success"])
        self.log.tag_configure("error", foreground=self.COLORS["danger"])
        self.log.tag_configure("muted", foreground=self.COLORS["muted"])
        self.log.tag_configure("strong", foreground=self.COLORS["text"])
        self.log.grid(row=1, column=0, sticky="nsew")

        scroll = self.ttk.Scrollbar(
            box,
            orient=self.tk.VERTICAL,
            command=self.log.yview,
        )
        scroll.grid(row=1, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)

        return box

    def build_footer(self, parent: Any) -> None:
        """构建底部状态栏。"""

        bottom = self.ttk.Frame(parent, style="App.TFrame")
        bottom.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        bottom.columnconfigure(0, weight=1)

        self.ttk.Label(
            bottom,
            textvariable=self.status_var,
            style="Status.TLabel",
        ).grid(row=0, column=0, sticky="w")
        self.open_dir_btn = self.ttk.Button(
            bottom,
            text="打开保存目录",
            command=self.open_output_dir,
            state=self.tk.DISABLED,
        )
        self.open_dir_btn.grid(row=0, column=1, sticky="e")

    def create_panel(self, parent: Any) -> Any:
        """创建轻量面板。"""

        panel = self.tk.Frame(
            parent,
            bg=self.COLORS["panel"],
            highlightthickness=1,
            highlightbackground=self.COLORS["border"],
            bd=0,
            padx=14,
            pady=12,
        )
        return panel

    def add_files(self) -> None:
        """添加 Excel 文件。"""

        from tkinter import filedialog

        picked = filedialog.askopenfilenames(
            title="选择 Excel 文件",
            filetypes=[("Excel", "*.xlsx *.xls")],
        )
        self.add_paths(picked)

    def add_paths(self, paths: Iterable[str | Path]) -> None:
        """添加文件或文件夹路径。"""

        files = expand_targets(paths)
        if not files:
            self.status_var.set("没有找到可处理的 Excel 文件")
            return

        existing_paths = {str(path.resolve()) for path in self.files}
        for file_path in files:
            resolved_path = str(file_path.resolve())
            if resolved_path in existing_paths:
                continue

            self.files.append(file_path)
            existing_paths.add(resolved_path)

        if self.output_dir is None and self.files:
            self.output_dir = default_output_dir(self.files)
            self.output_var.set(f"保存目录: {self.output_dir}")

        self.refresh_file_list()

    def clear_files(self) -> None:
        """清空待处理文件。"""

        self.files.clear()
        self.refresh_file_list()
        self.status_var.set("已清空")

    def choose_output_dir(self) -> None:
        """选择输出目录。"""

        from tkinter import filedialog

        folder = filedialog.askdirectory(title="选择保存目录")
        if folder:
            self.output_dir = Path(folder)
            self.output_var.set(f"保存目录: {self.output_dir}")

    def refresh_file_list(self) -> None:
        """刷新待处理文件列表。"""

        for item in self.file_list.get_children():
            self.file_list.delete(item)
        for file_path in self.files:
            self.file_list.insert(
                "",
                self.tk.END,
                values=(file_path.name, str(file_path.parent)),
            )

        self.count_var.set(f"{len(self.files)} 个文件")
        if self.files:
            self.status_var.set("文件已就绪")
        else:
            self.status_var.set("请选择 Excel 文件或文件夹")

    def set_running(self, running: bool) -> None:
        """切换按钮运行状态。"""

        state = self.tk.DISABLED if running else self.tk.NORMAL
        for button in (
            self.add_files_btn,
            self.clear_btn,
            self.output_btn,
            self.run_btn,
            self.clear_log_btn,
        ):
            button.configure(state=state)

    def append_log(self, text: str) -> None:
        """追加日志文本。"""

        tag = "muted"
        if text.startswith(("OK", "完成", "文件完成", "写出结果")):
            tag = "success"
        elif text.startswith(("x", "文件出错", "处理线程异常")) or "出错" in text:
            tag = "error"
        elif text.startswith(("开始筛选", "处理文件", "读取工作簿")):
            tag = "strong"

        self.log.configure(state="normal")
        self.log.insert(self.tk.END, text + "\n", tag)
        self.log.see(self.tk.END)
        self.log.configure(state="disabled")

    def clear_log(self) -> None:
        """清空处理日志。"""

        self.log.configure(state="normal")
        self.log.delete("1.0", self.tk.END)
        self.log.configure(state="disabled")

    def append_log_from_worker(self, text: str) -> None:
        """从后台线程追加日志到队列。"""

        self.log_queue.put(text)

    def poll_worker_events(self) -> None:
        """在主线程中轮询后台线程事件并更新界面。"""

        while True:
            try:
                self.append_log(self.log_queue.get_nowait())
            except Empty:
                break

        try:
            results = self.result_queue.get_nowait()
        except Empty:
            results = None

        if results is not None:
            self.processing_done(results)
            return

        if self.processing_active:
            self.root.after(100, self.poll_worker_events)

    def start_processing(self) -> None:
        """启动后台处理线程。"""

        from tkinter import messagebox

        if not self.files:
            messagebox.showwarning(APP_NAME, "请先添加 Excel 文件或文件夹。")
            return
        if self.output_dir is None:
            messagebox.showwarning(APP_NAME, "请先选择保存目录。")
            return

        files = list(self.files)
        output_dir = self.output_dir

        self.set_running(True)
        self.processing_active = True
        self.open_dir_btn.configure(state=self.tk.DISABLED)
        self.status_var.set("正在筛选...")
        self.append_log(f"开始筛选 {len(files)} 个文件 -> {output_dir}")

        thread = threading.Thread(
            target=self.process_worker,
            args=(files, output_dir),
            daemon=True,
        )
        thread.start()
        self.root.after(100, self.poll_worker_events)

    def process_worker(self, files: list[Path], out_dir: Path) -> None:
        """后台处理文件，完成后切回主线程更新 UI。"""

        try:
            results = filter_files(
                files,
                out_dir,
                progress_callback=self.append_log_from_worker,
            )
        except Exception as error:
            self.append_log_from_worker(f"处理线程异常: {error}")
            results = [
                FileResult(src=file_path, out=None, kept=0, error=str(error))
                for file_path in files
            ]

        self.result_queue.put(results)

    def processing_done(self, results: list[FileResult]) -> None:
        """处理完成后更新 UI。"""

        self.processing_active = False
        total = sum(result.kept for result in results)
        errors = sum(1 for result in results if result.error)

        for result in results:
            if result.error:
                self.append_log(f"x {result.src.name}: {result.error}")
            elif result.kept and result.out is not None:
                self.append_log(
                    f"OK {result.src.name}: 保留 {result.kept} 行 -> "
                    f"{result.out.name}"
                )
            else:
                self.append_log(f"- {result.src.name}: 保留 0 行")

        self.append_log(
            f"完成: 文件 {len(results)} 个, 保留 {total} 行, "
            f"出错 {errors} 个"
        )
        self.status_var.set(f"完成: 保留 {total} 行, 出错 {errors} 个")
        self.set_running(False)
        self.open_dir_btn.configure(state=self.tk.NORMAL)
        self.files.clear()
        self.refresh_file_list()
        self.status_var.set(f"完成: 保留 {total} 行, 出错 {errors} 个")

    def open_output_dir(self) -> None:
        """打开输出目录。"""

        if self.output_dir:
            open_folder(self.output_dir)


def run_gui() -> int:
    """运行 GUI 模式。"""

    try:
        import tkinter as tk
    except Exception as error:
        print(f"无法启动 GUI: {error}")
        return 1

    root = tk.Tk()
    CottonFilterApp(root)
    root.mainloop()
    return 0
