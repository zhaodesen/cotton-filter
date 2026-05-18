"""Data models and type aliases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


ColumnMap = dict[str, int]
Record = dict[str, Any]


@dataclass(frozen=True)
class ProcessedRow:
    """单行 Excel 数据的规则处理结果和原始行。"""

    record: Record
    raw_row: pd.Series
    excel_row_number: int


@dataclass(frozen=True)
class SheetProcessResult:
    """单个 sheet 的筛选结果和识别异常。"""

    normal_frame: pd.DataFrame
    issue_frame: pd.DataFrame


@dataclass(frozen=True)
class FileResult:
    """单个文件的处理结果。"""

    src: Path
    out: Path | None
    kept: int
    error: str | None = None
