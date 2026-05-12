"""
棉花报价表筛选脚本

用法:
    python3 cotton_filter.py 单个文件.xlsx
    python3 cotton_filter.py 文件夹/         # 批量处理整个文件夹
    python3 cotton_filter.py --watch 文件夹/ # 监听文件夹, 新文件自动处理
"""
import re
import sys
from pathlib import Path
import pandas as pd

# ---- 列名(可根据实际表头微调) ----
COL_COLOR  = "颜色级"
COL_LENGTH = "长度"
COL_STRENGTH = "强力"
COL_MIC   = "马值"
COL_UNIF  = "整齐度"
COL_BASIS = "基差"


def extract_max_color_pct(text: str) -> float:
    """从 '白棉2级:2.2%，白棉3级:95.7%，白棉4级:2.1%' 中取最大那个百分比.
    返回 0.0 表示无法解析."""
    if not isinstance(text, str):
        return 0.0
    nums = re.findall(r"(\d+(?:\.\d+)?)\s*%", text)
    return max((float(n) for n in nums), default=0.0)


def score_row(row) -> int:
    """
    TODO: 由用户实现 —— 这是你领域知识最值钱的地方.
    根据 row 的各字段返回总分(整数).
    可用字段: row[COL_COLOR], row[COL_LENGTH], row[COL_STRENGTH],
              row[COL_MIC], row[COL_UNIF]
    辅助函数: extract_max_color_pct(row[COL_COLOR])

    规则提醒(请在实现时明确边界 > 还是 >=):
      颜色级最大档 >= 80%          : +100
      长度 > 30                    : +400
      长度 在 29~30                : +150     # 含端点? 重叠时取哪个?
      马值 < 4.2                   : +100
      马值 > 5                     : -100
      整齐度 > 83                  : +200
      强力 > 31                    : +250
      强力 在 29~31                : +150
    """
    score = 0
    if extract_max_color_pct(row[COL_COLOR]) >= 80:
        score += 100

    length = row[COL_LENGTH] or 0
    if length > 30:
        score += 400
    elif 29 <= length <= 30:
        score += 150

    mic = row[COL_MIC] or 0
    if mic < 4.2:
        score += 100
    elif mic > 5:
        score -= 100

    if (row[COL_UNIF] or 0) > 83:
        score += 200

    s = row[COL_STRENGTH] or 0
    if s > 31:
        score += 250
    elif 29 <= s <= 31:
        score += 150

    return score


def filter_file(src: Path, dst: Path) -> int:
    """读 src, 评分+过滤, 写 dst. 返回保留行数."""
    df = pd.read_excel(src)
    # 跳过空行
    df = df.dropna(subset=[COL_BASIS]).copy()

    df["得分"] = df.apply(score_row, axis=1)
    # 保留条件: 得分 < 基差 且 (基差 - 得分) <= 200
    diff = df[COL_BASIS] - df["得分"]
    kept = df[(diff > 0) & (diff <= 200)].copy()
    kept["与基差差距"] = diff[kept.index]

    kept.to_excel(dst, index=False)
    return len(kept)


def _open_folder(p: Path):
    """跨平台打开文件夹."""
    import subprocess, platform
    sysname = platform.system()
    if sysname == "Windows":
        import os; os.startfile(p)
    elif sysname == "Darwin":
        subprocess.run(["open", str(p)])
    else:
        subprocess.run(["xdg-open", str(p)])


def main():
    args = sys.argv[1:]
    if not args:
        # 双击 exe / 无参数运行 -> 弹窗选文件
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk(); root.withdraw()
            picked = filedialog.askopenfilenames(
                title="选择 Excel 报价表",
                filetypes=[("Excel", "*.xlsx *.xls")])
            args = list(picked)
        except Exception:
            print(__doc__); input("按回车退出..."); sys.exit(1)
        if not args:
            sys.exit(0)

    out_dirs = []
    total = 0
    for a in args:
        target = Path(a)
        if not target.exists():
            print(f"✗ 跳过(不存在): {target}"); continue
        out_dir = target.parent / "筛选结果" if target.is_file() else target / "筛选结果"
        out_dir.mkdir(exist_ok=True)
        out_dirs.append(out_dir)

        files = [target] if target.is_file() else sorted(target.glob("*.xlsx"))
        for f in files:
            if f.parent.name == "筛选结果":
                continue
            out = out_dir / f"筛选_{f.name}"
            try:
                n = filter_file(f, out)
                total += 1
                print(f"✓ {f.name}  保留 {n} 行 → {out.name}")
            except Exception as e:
                print(f"✗ {f.name}  出错: {e}")

    # 自动打开第一个输出目录
    if out_dirs:
        _open_folder(out_dirs[0])

    print(f"\n共处理 {total} 个文件. 窗口将在 3 秒后关闭...")
    import time; time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[错误] {e}")
        input("按回车退出...")
