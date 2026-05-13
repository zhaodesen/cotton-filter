"""Tkinter GUI for cotton-filter."""

from __future__ import annotations

import threading
import sys
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Iterable

from .build_info import BUILD_VERSION
from .constants import APP_NAME
from .file_utils import (
    default_output_dir,
    expand_targets,
    filter_files,
    open_folder,
)
from .models import FileResult
from .updater import download_update, get_update_info, install_update_and_restart


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
        self.tray_icon: Any = None
        self.tray_thread: threading.Thread | None = None
        self.is_quitting = False
        self.is_windows = sys.platform.startswith("win")
        self.display_version = self.format_display_version(BUILD_VERSION)
        self.display_name = f"{APP_NAME} {self.display_version}"

        self.status_var = tk.StringVar(value="请选择 Excel 文件或文件夹")
        self.output_var = tk.StringVar(value="未选择保存目录")
        self.count_var = tk.StringVar(value="0 个文件")

        self.add_files_btn: Any = None
        self.clear_btn: Any = None
        self.output_btn: Any = None
        self.run_btn: Any = None
        self.clear_log_btn: Any = None
        self.open_dir_btn: Any = None
        self.update_btn: Any = None
        self.file_list: Any = None
        self.log: Any = None

        self.configure_root()
        self.configure_styles()
        self.build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self.handle_close)

    def configure_root(self) -> None:
        """设置主窗口。"""

        self.root.title(self.display_name)
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

        self.ttk.Label(header, text=f"Excel 筛选工具 {self.display_version}", style="Title.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.update_btn = self.ttk.Button(
            header,
            text="检查更新",
            command=self.start_update_check,
        )
        self.update_btn.grid(row=0, column=1, sticky="e", padx=(12, 0))


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

        self.run_btn = self.ttk.Button(
            actions,
            text="开始筛选",
            command=self.start_processing,
            style="Primary.TButton",
        )
        self.run_btn.grid(row=0, column=1, padx=(6, 8))

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
        ).grid(row=0, column=1, sticky="e", padx=(0, 10))
        self.clear_btn = self.ttk.Button(
            header,
            text="清空",
            command=self.clear_files,
        )
        self.clear_btn.grid(row=0, column=2, sticky="e")

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
        self.output_btn = self.ttk.Button(
            bottom,
            text="选择保存目录",
            command=self.choose_output_dir,
        )
        self.output_btn.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.open_dir_btn = self.ttk.Button(
            bottom,
            text="打开保存目录",
            command=self.open_output_dir,
            state=self.tk.DISABLED,
        )
        self.open_dir_btn.grid(row=0, column=2, sticky="e")

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

    def format_display_version(self, version: str) -> str:
        """格式化 GUI 展示版本。"""

        cleaned = version.strip()
        if not cleaned:
            cleaned = "dev"
        if cleaned.lower() == "dev":
            return "dev"
        if cleaned.lower().startswith("v"):
            return cleaned
        return f"v{cleaned}"

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
            self.update_btn,
        ):
            button.configure(state=state)

    def append_log(self, text: str) -> None:
        """追加日志文本。"""

        tag = "muted"
        if text.startswith(("成功", "完成")):
            tag = "success"
        elif text.startswith(("失败", "处理线程异常")) or "失败" in text:
            tag = "error"
        elif text.startswith("开始筛选"):
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
        self.append_log(f"开始筛选: {len(files)} 个文件")

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
            results = filter_files(files, out_dir)
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
                self.append_log(f"失败: {result.src.name}，{result.error}")
            elif result.kept and result.out is not None:
                self.append_log(f"成功: {result.src.name}，筛出 {result.kept} 行")
            else:
                self.append_log(f"成功: {result.src.name}，筛出 0 行")

        self.append_log(
            f"完成: 成功 {len(results) - errors} 个，失败 {errors} 个，"
            f"共筛出 {total} 行"
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

    def start_update_check(self) -> None:
        """手动后台检查 Windows 更新。"""

        self.update_btn.configure(state=self.tk.DISABLED)
        self.status_var.set("正在检查更新...")
        thread = threading.Thread(target=self.update_check_worker, daemon=True)
        thread.start()

    def update_check_worker(self) -> None:
        """检查更新，避免阻塞 Tk 主线程。"""

        try:
            update = get_update_info()
        except Exception as error:
            self.root.after(0, lambda: self.show_update_check_error(error))
            return

        if update is not None:
            self.root.after(0, lambda: self.prompt_update(update))
            return

        self.root.after(0, self.show_no_update)

    def show_no_update(self) -> None:
        """提示当前无需更新。"""

        from tkinter import messagebox

        self.update_btn.configure(state=self.tk.NORMAL)
        self.status_var.set("当前已是最新版本")
        messagebox.showinfo(APP_NAME, "当前已是最新版本。")

    def show_update_check_error(self, error: Exception) -> None:
        """显示检查更新失败提示。"""

        from tkinter import messagebox

        self.update_btn.configure(state=self.tk.NORMAL)
        self.status_var.set("检查更新失败")
        detail = str(error) or error.__class__.__name__
        messagebox.showerror(APP_NAME, f"检查更新失败: {detail}")

    def prompt_update(self, update: Any) -> None:
        """提示用户下载并安装新版本。"""

        from tkinter import messagebox

        self.status_var.set(f"发现新版本: {update.version}")
        should_update = messagebox.askyesno(
            APP_NAME,
            "发现新版本，是否现在下载并重启更新？",
        )
        if not should_update:
            self.update_btn.configure(state=self.tk.NORMAL)
            self.status_var.set("已取消更新")
            return

        self.update_btn.configure(state=self.tk.DISABLED)
        self.status_var.set("正在下载更新...")
        thread = threading.Thread(target=self.install_update_worker, args=(update,), daemon=True)
        thread.start()

    def install_update_worker(self, update: Any) -> None:
        """下载更新并触发替换重启。"""

        try:
            downloaded_exe = download_update(update)
            install_update_and_restart(downloaded_exe)
        except Exception as error:
            self.root.after(0, lambda: self.show_update_error(error))
            return

        self.root.after(0, self.quit_app)

    def show_update_error(self, error: Exception) -> None:
        """显示更新失败提示。"""

        from tkinter import messagebox

        self.status_var.set("更新失败")
        self.update_btn.configure(state=self.tk.NORMAL)
        detail = str(error) or error.__class__.__name__
        messagebox.showerror(APP_NAME, f"更新失败: {detail}")

    def handle_close(self) -> None:
        """处理窗口关闭按钮。"""

        if self.is_windows:
            self.minimize_to_tray()
            return

        self.quit_app()

    def minimize_to_tray(self) -> None:
        """隐藏主窗口并保留 Windows 托盘入口。"""

        self.ensure_tray_icon()
        self.root.withdraw()

    def show_window(self) -> None:
        """从托盘恢复主窗口。"""

        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def quit_app(self) -> None:
        """退出应用并清理托盘图标。"""

        if self.is_quitting:
            return

        self.is_quitting = True
        if self.tray_icon is not None:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.destroy()

    def ensure_tray_icon(self) -> None:
        """首次最小化时创建托盘图标。"""

        if self.tray_icon is not None:
            return

        import pystray
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (64, 64), "#166c5f")
        draw = ImageDraw.Draw(image)
        draw.ellipse((16, 13, 48, 45), fill="#ffffff")
        draw.rectangle((28, 39, 36, 52), fill="#ffffff")

        menu = pystray.Menu(
            pystray.MenuItem(
                "打开 cotton-filter",
                lambda _icon, _item: self.root.after(0, self.show_window),
                default=True,
            ),
            pystray.MenuItem(
                "退出",
                lambda _icon, _item: self.root.after(0, self.quit_app),
            ),
        )
        self.tray_icon = pystray.Icon(APP_NAME, image, APP_NAME, menu)
        self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        self.tray_thread.start()


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
