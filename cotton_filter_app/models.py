"""Data models and type aliases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


ColumnMap = dict[str, int]
Record = dict[str, Any]


@dataclass(frozen=True)
class FileResult:
    """单个文件的处理结果。"""

    src: Path
    out: Path | None
    kept: int
    error: str | None = None
