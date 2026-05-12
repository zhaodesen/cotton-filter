"""
cotton-filter
- 自动定位表头行,容忍前置公司抬头/业务员等非数据行
- 列名通过别名表对齐, 支持多家公司模板
- 支持 .xlsx 和 .xls
- 支持 GUI 批量处理, 也支持命令行传入文件/文件夹

新增模板支持只需在 COLUMN_ALIASES 中加一行别名.
"""
from __future__ import annotations

import re
import sys
import threading
import unicodedata
from pathlib import Path
import pandas as pd


APP_NAME = "cotton-filter"
RESULT_DIR_NAME = "cotton-filter-results"
OUTPUT_PREFIX = "filtered_"
EXCEL_SUFFIXES = {".xlsx", ".xls"}


# ====== 字段别名表 (key 为统一字段名,value 为可能出现的列名) ======
COLUMN_ALIASES = {
    "基差":   ["基差"],
    "颜色级": ["颜色级", "颜色级占比", "颜色级别", "颜色级/品级", "颜色级品级", "色级", "品级"],
    "长度":   ["长度", "平均长度"],
    "强力":   ["强力", "比强", "强度", "断裂比强度"],
    "马值":   ["马值", "码值", "平均马值", "平均码值", "马克隆", "马克隆值", "mic", "mic值"],
    "整齐度": ["整齐度", "长整", "整齐度指数", "长度整齐度", "平均整齐度"],
    # 输出时能带上方便核对的标识列
    "批号":   ["批号"],
}
REQUIRED = ["基差", "长度", "马值"]  # 缺这些列直接跳过该 sheet
COLUMN_EXCLUDES = {
    "长度": ["整齐", "长整", "强", "马", "码", "颜色", "色级", "品级"],
}


def normalize_text(x):
    """统一大小写/全半角/空白/常见标点, 用于列名对齐."""
    if x is None:
        return ""
    s = unicodedata.normalize("NFKC", str(x)).strip().lower()
    s = re.sub(r"[\s\u3000]+", "", s)
    s = re.sub(r"[()（）【】\[\]{}<>《》:：/\\_\-—]+", "", s)
    return s


def _field_match_score(std_name: str, cell: str, alias: str) -> int:
    """字段级匹配分数. 0 表示不匹配; 分数越高越可靠."""
    if not cell or not alias:
        return 0
    if any(bad in cell for bad in COLUMN_EXCLUDES.get(std_name, [])):
        return 0
    if cell == alias:
        return 1000 + len(alias)
    if cell.startswith(alias) or cell.endswith(alias):
        return 700 + len(alias)
    if alias in cell:
        return 600 + len(alias)
    if len(cell) >= 2 and cell in alias:
        return 500 + len(cell)
    return 0


def find_header_row(df_raw: pd.DataFrame, max_scan: int = 30) -> int:
    """在前 max_scan 行里找包含最多目标关键字的那一行作为表头.
    返回行号 (0-indexed); 找不到返回 -1."""
    best_row, best_score = -1, 0
    for i in range(min(max_scan, len(df_raw))):
        mapping = build_column_map(df_raw.iloc[i].tolist())
        required_hits = sum(1 for k in REQUIRED if k in mapping)
        score = required_hits * 100 + len(mapping)
        if score > best_score:
            best_score, best_row = score, i
    # 至少命中必需字段, 才算找到表头.
    return best_row if best_score >= len(REQUIRED) * 100 else -1


def build_column_map(header_cells) -> dict:
    """根据实际表头, 返回 {统一字段名: 实际列索引} ."""
    norm_cells = [normalize_text(c) for c in header_cells]
    candidates = []
    for std_name, aliases in COLUMN_ALIASES.items():
        for idx, cell in enumerate(norm_cells):
            for alias in aliases:
                a = normalize_text(alias)
                score = _field_match_score(std_name, cell, a)
                if score:
                    candidates.append((score, len(a), -idx, std_name, idx))

    mapping = {}
    used_cols = set()
    for _, _, _, std_name, idx in sorted(candidates, reverse=True):
        if std_name not in mapping and idx not in used_cols:
            mapping[std_name] = idx
            used_cols.add(idx)
    return mapping


# ====== 颜色级解析 ======
PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[%％]")

def extract_max_color_pct(text) -> float:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return 0.0
    s = str(text)
    nums = PCT_RE.findall(s)
    return max((float(n) for n in nums), default=0.0)


# ====== 评分规则 ======
def score_record(rec: dict) -> int:
    """rec 是 {统一字段名: 原始值} 的字典."""
    def num(v, default=0.0):
        if v is None or pd.isna(v):
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    score = 0
    if extract_max_color_pct(rec.get("颜色级")) >= 80:
        score += 100

    length = num(rec.get("长度"))
    if length > 30:
        score += 400
    elif 29 <= length <= 30:
        score += 150

    mic = num(rec.get("马值"))
    if mic and mic < 4.2:
        score += 100
    elif mic > 5:
        score -= 100

    if num(rec.get("整齐度")) > 83:
        score += 200

    s = num(rec.get("强力"))
    if s > 31:
        score += 250
    elif 29 <= s <= 31:
        score += 150

    return score


# ====== 单个 sheet 处理 ======
def process_sheet(df_raw: pd.DataFrame) -> pd.DataFrame | None:
    """返回处理后的 DataFrame; sheet 不像数据表则返回 None."""
    hdr = find_header_row(df_raw)
    if hdr < 0:
        return None
    col_map = build_column_map(df_raw.iloc[hdr].tolist())
    if not all(k in col_map for k in REQUIRED):
        return None

    body = df_raw.iloc[hdr + 1:].reset_index(drop=True)

    records = []
    for _, row in body.iterrows():
        basis_raw = row.iloc[col_map["基差"]]
        try:
            basis = float(basis_raw)
        except (TypeError, ValueError):
            continue  # 跳过空行 / 汇总行 / 文本行

        rec = {std: row.iloc[idx] for std, idx in col_map.items()}
        rec["_基差"] = basis
        rec["_得分"] = score_record(rec)
        rec["_与基差差距"] = basis - rec["_得分"]
        records.append(rec)

    if not records:
        return None
    df = pd.DataFrame(records)
    kept = df[(df["_与基差差距"] > 0) & (df["_与基差差距"] <= 200)].copy()
    # 重命名输出列
    kept = kept.rename(columns={"_得分": "得分", "_与基差差距": "与基差差距"})
    cols = ["批号", "基差", "得分", "与基差差距", "长度", "强力", "马值", "整齐度", "颜色级"]
    kept = kept[[c for c in cols if c in kept.columns]]
    return kept


def filter_file(src: Path, dst: Path) -> int:
    """读所有 sheet,合并保留行写出. 返回保留总行数."""
    xls = pd.ExcelFile(src)
    parts = []
    for sn in xls.sheet_names:
        df_raw = pd.read_excel(src, sheet_name=sn, header=None)
        result = process_sheet(df_raw)
        if result is not None and len(result):
            result.insert(0, "来源sheet", sn)
            parts.append(result)
    if not parts:
        return 0
    out = pd.concat(parts, ignore_index=True)
    out.to_excel(dst, index=False)
    return len(out)


def unique_output_path(out_dir: Path, src: Path) -> Path:
    """生成不覆盖既有文件的输出路径."""
    base = f"{OUTPUT_PREFIX}{src.stem}"
    candidate = out_dir / f"{base}.xlsx"
    i = 2
    while candidate.exists():
        candidate = out_dir / f"{base}_{i}.xlsx"
        i += 1
    return candidate


def filter_files(files: list[Path], out_dir: Path) -> list[dict]:
    """批量处理文件, 返回每个文件的处理结果."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for src in files:
        try:
            out = unique_output_path(out_dir, src)
            kept = filter_file(src, out)
            if kept == 0 and out.exists():
                out.unlink()
            results.append({"src": src, "out": out if kept else None, "kept": kept, "error": None})
        except Exception as e:
            results.append({"src": src, "out": None, "kept": 0, "error": str(e)})
    return results


# ====== 入口 ======
def _open_folder(p: Path):
    import subprocess, platform
    sys_ = platform.system()
    if sys_ == "Windows":
        import os; os.startfile(p)
    elif sys_ == "Darwin":
        subprocess.run(["open", str(p)])
    else:
        subprocess.run(["xdg-open", str(p)])


def _expand_targets(args):
    """把混合的文件/文件夹参数展开成所有待处理的 xlsx/xls 文件."""
    files = []
    for a in args:
        p = Path(a)
        if not p.exists():
            print(f"x 跳过(不存在): {p}"); continue
        if p.is_file():
            if p.suffix.lower() in EXCEL_SUFFIXES:
                files.append(p)
        else:
            for ext in ("*.xlsx", "*.xls"):
                files.extend(sorted(p.glob(ext)))
    # 去重 + 排除我们自己生成的输出
    seen = set(); uniq = []
    for f in files:
        if f.parent.name == RESULT_DIR_NAME or f.name.startswith(OUTPUT_PREFIX):
            continue
        key = str(f.resolve())
        if key in seen: continue
        seen.add(key); uniq.append(f)
    return uniq


def run_cli(args: list[str], out_dir: Path | None = None) -> int:
    files = _expand_targets(args)
    if not files:
        print("没有可处理的 Excel 文件")
        return 0

    out_dir = out_dir or (files[0].parent / RESULT_DIR_NAME)
    results = filter_files(files, out_dir)
    total = sum(r["kept"] for r in results)
    errors = 0

    for r in results:
        if r["error"]:
            errors += 1
            print(f"x {r['src'].name}  出错: {r['error']}")
        elif r["kept"]:
            print(f"OK {r['src'].name}  保留 {r['kept']} 行 -> {r['out'].name}")
        else:
            print(f"- {r['src'].name}  保留 0 行")

    _open_folder(out_dir)
    print(f"\n共处理 {len(results)} 个文件, 保留 {total} 行, 出错 {errors} 个.")
    return 1 if errors else 0


class CottonFilterApp:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.root = root
        self.files: list[Path] = []
        self.output_dir: Path | None = None

        root.title(APP_NAME)
        root.geometry("760x560")
        root.minsize(680, 500)

        self.status_var = tk.StringVar(value="请选择 Excel 文件或文件夹")
        self.output_var = tk.StringVar(value="未选择保存目录")
        self.count_var = tk.StringVar(value="0 个文件")

        frame = ttk.Frame(root, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)

        title = ttk.Label(frame, text=APP_NAME, font=("Arial", 20, "bold"))
        title.grid(row=0, column=0, sticky="w")

        actions = ttk.Frame(frame)
        actions.grid(row=1, column=0, sticky="ew", pady=(14, 10))
        for i in range(6):
            actions.columnconfigure(i, weight=0)
        actions.columnconfigure(5, weight=1)

        self.add_files_btn = ttk.Button(actions, text="添加 Excel", command=self.add_files)
        self.add_files_btn.grid(row=0, column=0, padx=(0, 8))
        self.add_folder_btn = ttk.Button(actions, text="添加文件夹", command=self.add_folder)
        self.add_folder_btn.grid(row=0, column=1, padx=(0, 8))
        self.clear_btn = ttk.Button(actions, text="清空", command=self.clear_files)
        self.clear_btn.grid(row=0, column=2, padx=(0, 8))
        self.output_btn = ttk.Button(actions, text="选择保存目录", command=self.choose_output_dir)
        self.output_btn.grid(row=0, column=3, padx=(0, 8))
        self.run_btn = ttk.Button(actions, text="开始处理", command=self.start_processing)
        self.run_btn.grid(row=0, column=4)

        summary = ttk.Frame(frame)
        summary.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        summary.columnconfigure(1, weight=1)
        ttk.Label(summary, textvariable=self.count_var).grid(row=0, column=0, sticky="w", padx=(0, 18))
        ttk.Label(summary, textvariable=self.output_var).grid(row=0, column=1, sticky="w")

        panes = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        panes.grid(row=3, column=0, sticky="nsew")

        files_box = ttk.Frame(panes)
        files_box.columnconfigure(0, weight=1)
        files_box.rowconfigure(1, weight=1)
        ttk.Label(files_box, text="待处理文件").grid(row=0, column=0, sticky="w")
        self.file_list = tk.Listbox(files_box, height=8, activestyle="none")
        self.file_list.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        files_scroll = ttk.Scrollbar(files_box, orient=tk.VERTICAL, command=self.file_list.yview)
        files_scroll.grid(row=1, column=1, sticky="ns", pady=(6, 0))
        self.file_list.configure(yscrollcommand=files_scroll.set)
        panes.add(files_box, weight=1)

        log_box = ttk.Frame(panes)
        log_box.columnconfigure(0, weight=1)
        log_box.rowconfigure(1, weight=1)
        ttk.Label(log_box, text="处理日志").grid(row=0, column=0, sticky="w")
        self.log = tk.Text(log_box, height=10, wrap="word", state="disabled")
        self.log.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        log_scroll = ttk.Scrollbar(log_box, orient=tk.VERTICAL, command=self.log.yview)
        log_scroll.grid(row=1, column=1, sticky="ns", pady=(6, 0))
        self.log.configure(yscrollcommand=log_scroll.set)
        panes.add(log_box, weight=1)

        bottom = ttk.Frame(frame)
        bottom.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        self.open_dir_btn = ttk.Button(bottom, text="打开保存目录", command=self.open_output_dir, state=tk.DISABLED)
        self.open_dir_btn.grid(row=0, column=1, sticky="e")

    def add_files(self):
        from tkinter import filedialog

        picked = filedialog.askopenfilenames(
            title="选择 Excel 文件",
            filetypes=[("Excel", "*.xlsx *.xls")],
        )
        self.add_paths(picked)

    def add_folder(self):
        from tkinter import filedialog

        folder = filedialog.askdirectory(title="选择包含 Excel 的文件夹")
        if folder:
            self.add_paths([folder])

    def add_paths(self, paths):
        files = _expand_targets(paths)
        if not files:
            self.status_var.set("没有找到可处理的 Excel 文件")
            return
        existing = {str(p.resolve()) for p in self.files}
        for f in files:
            key = str(f.resolve())
            if key not in existing:
                self.files.append(f)
                existing.add(key)
        if self.output_dir is None and self.files:
            self.output_dir = self.files[0].parent / RESULT_DIR_NAME
            self.output_var.set(f"保存目录: {self.output_dir}")
        self.refresh_file_list()

    def clear_files(self):
        self.files.clear()
        self.refresh_file_list()
        self.status_var.set("已清空")

    def choose_output_dir(self):
        from tkinter import filedialog

        folder = filedialog.askdirectory(title="选择保存目录")
        if folder:
            self.output_dir = Path(folder)
            self.output_var.set(f"保存目录: {self.output_dir}")

    def refresh_file_list(self):
        self.file_list.delete(0, self.tk.END)
        for f in self.files:
            self.file_list.insert(self.tk.END, str(f))
        self.count_var.set(f"{len(self.files)} 个文件")
        if self.files:
            self.status_var.set("文件已就绪")
        else:
            self.status_var.set("请选择 Excel 文件或文件夹")

    def set_running(self, running: bool):
        state = self.tk.DISABLED if running else self.tk.NORMAL
        for btn in (self.add_files_btn, self.add_folder_btn, self.clear_btn, self.output_btn, self.run_btn):
            btn.configure(state=state)

    def append_log(self, text: str):
        self.log.configure(state="normal")
        self.log.insert(self.tk.END, text + "\n")
        self.log.see(self.tk.END)
        self.log.configure(state="disabled")

    def start_processing(self):
        from tkinter import messagebox

        if not self.files:
            messagebox.showwarning(APP_NAME, "请先添加 Excel 文件或文件夹。")
            return
        if self.output_dir is None:
            messagebox.showwarning(APP_NAME, "请先选择保存目录。")
            return
        files = list(self.files)
        out_dir = self.output_dir
        self.set_running(True)
        self.open_dir_btn.configure(state=self.tk.DISABLED)
        self.status_var.set("正在处理...")
        self.append_log(f"开始处理 {len(files)} 个文件 -> {out_dir}")
        threading.Thread(target=self.process_worker, args=(files, out_dir), daemon=True).start()

    def process_worker(self, files: list[Path], out_dir: Path):
        results = filter_files(files, out_dir)
        self.root.after(0, self.processing_done, results, out_dir)

    def processing_done(self, results: list[dict], out_dir: Path):
        total = sum(r["kept"] for r in results)
        errors = sum(1 for r in results if r["error"])
        for r in results:
            if r["error"]:
                self.append_log(f"x {r['src'].name}: {r['error']}")
            elif r["kept"]:
                self.append_log(f"OK {r['src'].name}: 保留 {r['kept']} 行 -> {r['out'].name}")
            else:
                self.append_log(f"- {r['src'].name}: 保留 0 行")
        self.append_log(f"完成: 文件 {len(results)} 个, 保留 {total} 行, 出错 {errors} 个")
        self.status_var.set(f"完成: 保留 {total} 行, 出错 {errors} 个")
        self.set_running(False)
        self.open_dir_btn.configure(state=self.tk.NORMAL)

    def open_output_dir(self):
        if self.output_dir:
            _open_folder(self.output_dir)


def run_gui() -> int:
    try:
        import tkinter as tk
    except Exception as e:
        print(f"无法启动 GUI: {e}")
        return 1
    root = tk.Tk()
    CottonFilterApp(root)
    root.mainloop()
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args:
        return run_cli(args)
    return run_gui()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[错误] {e}")
        sys.exit(1)
