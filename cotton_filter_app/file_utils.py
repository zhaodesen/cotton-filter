"""File-system helpers for cotton-filter."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence

from .constants import EXCEL_SUFFIXES, RESULT_DIR_NAME
from .models import FileResult
from .processor import filter_file

ProgressLogger = Callable[[str], None]


def unique_output_path(out_dir: Path, src: Path) -> Path:
    """生成不覆盖既有文件的输出路径。"""

    candidate = out_dir / src.name
    counter = 2

    while candidate.exists():
        candidate = out_dir / f"{src.stem}_{counter}{src.suffix}"
        counter += 1

    return candidate


def iter_filter_files(
    files: Sequence[Path],
    out_dir: Path,
    log: ProgressLogger | None = None,
) -> Iterator[tuple[int, int, FileResult]]:
    """逐个处理文件，每完成一个就产出 (序号, 总数, 结果)。"""

    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(files)

    for index, src in enumerate(files, start=1):
        try:
            if log:
                log(f"处理文件 {index}/{total}: {src.name}")
            out = unique_output_path(out_dir, src)
            kept = filter_file(src, out, log=log)

            if kept == 0 and out.exists():
                out.unlink()

            result = FileResult(src=src, out=out if kept else None, kept=kept)
            if log:
                log(f"文件完成: {src.name}，保留 {kept} 行")
        except Exception as error:
            if log:
                log(f"文件出错: {src.name}，{error}")
            result = FileResult(src=src, out=None, kept=0, error=str(error))

        yield index, total, result


def filter_files(
    files: Sequence[Path],
    out_dir: Path,
    progress_callback: ProgressLogger | None = None,
) -> list[FileResult]:
    """批量处理文件。"""

    return [
        result
        for _, _, result in iter_filter_files(
            files, out_dir, log=progress_callback
        )
    ]


def iter_excel_files(path: Path) -> Iterable[Path]:
    """从文件或目录中枚举 Excel 文件。"""

    if path.is_file():
        if path.suffix.lower() in EXCEL_SUFFIXES:
            yield path
        return

    for pattern in ("*.xlsx", "*.xls"):
        yield from sorted(path.glob(pattern))


def expand_targets(args: Iterable[str | Path]) -> list[Path]:
    """把混合的文件/文件夹参数展开成待处理 Excel 文件。"""

    files: list[Path] = []

    for arg in args:
        path = Path(arg)
        if not path.exists():
            print(f"x 跳过(不存在): {path}")
            continue
        files.extend(iter_excel_files(path))

    unique_files: list[Path] = []
    seen: set[str] = set()

    for file_path in files:
        if file_path.parent.name == RESULT_DIR_NAME:
            continue

        resolved_path = str(file_path.resolve())
        if resolved_path in seen:
            continue

        seen.add(resolved_path)
        unique_files.append(file_path)

    return unique_files


def default_output_dir(files: Sequence[Path]) -> Path:
    """根据首个输入文件生成默认输出目录。"""

    return files[0].parent / RESULT_DIR_NAME
