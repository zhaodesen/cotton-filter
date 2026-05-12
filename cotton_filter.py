"""
棉花报价表筛选 (通用版)
- 自动定位表头行,容忍前置公司抬头/业务员等非数据行
- 列名通过别名表对齐, 支持多家公司模板
- 支持 .xlsx 和 .xls
- 拖拽多文件、文件夹 / 双击弹窗

新增模板支持只需在 COLUMN_ALIASES 中加一行别名.
"""
import re
import sys
from pathlib import Path
import pandas as pd


# ====== 字段别名表 (key 为统一字段名,value 为可能出现的列名) ======
COLUMN_ALIASES = {
    "基差":   ["基差"],
    "颜色级": ["颜色级", "颜色级占比", "颜色级别"],
    "长度":   ["长度"],
    "强力":   ["强力", "比强", "强度"],
    "马值":   ["马值"],
    "整齐度": ["整齐度", "长整", "整齐度指数"],
    # 输出时能带上方便核对的标识列
    "批号":   ["批号"],
}
REQUIRED = ["基差", "长度", "马值"]  # 缺这些列直接跳过该 sheet


def normalize_text(x):
    """去空白、全角转半角、小写化, 用于列名对齐."""
    if x is None:
        return ""
    s = str(x).strip()
    # 全角符号常见替换
    s = s.replace("％", "%")
    return s


def find_header_row(df_raw: pd.DataFrame, max_scan: int = 30) -> int:
    """在前 max_scan 行里找包含最多目标关键字的那一行作为表头.
    返回行号 (0-indexed); 找不到返回 -1."""
    keywords = set()
    for aliases in COLUMN_ALIASES.values():
        keywords.update(normalize_text(a) for a in aliases)

    best_row, best_hits = -1, 0
    for i in range(min(max_scan, len(df_raw))):
        cells = [normalize_text(v) for v in df_raw.iloc[i].tolist()]
        hits = sum(1 for c in cells if c in keywords)
        if hits > best_hits:
            best_hits, best_row = hits, i
    # 至少命中 3 个关键字才算找到表头
    return best_row if best_hits >= 3 else -1


def build_column_map(header_cells) -> dict:
    """根据实际表头, 返回 {统一字段名: 实际列索引} ."""
    norm_cells = [normalize_text(c) for c in header_cells]
    mapping = {}
    for std_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            a = normalize_text(alias)
            if a in norm_cells:
                mapping[std_name] = norm_cells.index(a)
                break
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
    """返回筛选后的 DataFrame; sheet 不像数据表则返回 None."""
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
            print(f"✗ 跳过(不存在): {p}"); continue
        if p.is_file():
            if p.suffix.lower() in (".xlsx", ".xls"):
                files.append(p)
        else:
            for ext in ("*.xlsx", "*.xls"):
                files.extend(sorted(p.glob(ext)))
    # 去重 + 排除我们自己生成的输出
    seen = set(); uniq = []
    for f in files:
        if f.parent.name == "筛选结果" or f.name.startswith("筛选_"):
            continue
        key = str(f.resolve())
        if key in seen: continue
        seen.add(key); uniq.append(f)
    return uniq


def main():
    args = sys.argv[1:]
    if not args:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk(); root.withdraw()
            picked = filedialog.askopenfilenames(
                title="选择 Excel 报价表 (可多选)",
                filetypes=[("Excel", "*.xlsx *.xls")])
            args = list(picked)
        except Exception:
            print(__doc__); input("按回车退出..."); sys.exit(1)
        if not args:
            sys.exit(0)

    files = _expand_targets(args)
    if not files:
        print("没有可处理的 Excel 文件"); input("按回车退出..."); sys.exit(0)

    out_dir = files[0].parent / "筛选结果"
    out_dir.mkdir(exist_ok=True)

    total = 0
    for f in files:
        try:
            out = out_dir / f"筛选_{f.stem}.xlsx"
            n = filter_file(f, out)
            total += n
            print(f"✓ {f.name}  保留 {n} 行 → {out.name}")
        except Exception as e:
            print(f"✗ {f.name}  出错: {e}")

    _open_folder(out_dir)
    print(f"\n共保留 {total} 行. 窗口将在 3 秒后关闭...")
    import time; time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[错误] {e}")
        input("按回车退出...")
