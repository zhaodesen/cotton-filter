"""Excel header detection and column mapping."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Sequence

import pandas as pd

from .constants import (
    COLUMN_ALIASES,
    COLUMN_EXCLUDES,
    HEADER_SCAN_ROWS,
    REQUIRED_COLUMNS,
)
from .models import ColumnMap


HEADER_PUNCTUATION_RE = re.compile(r"[\s\u3000]+")
HEADER_SYMBOL_RE = re.compile(r"[()（）【】\[\]{}<>《》:：/\\_\-—]+")


def normalize_text(value: Any) -> str:
    """标准化表头文本，用于字段别名匹配。"""

    if value is None:
        return ""

    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    text = HEADER_PUNCTUATION_RE.sub("", text)
    return HEADER_SYMBOL_RE.sub("", text)


def field_match_score(field_name: str, cell_text: str, alias_text: str) -> int:
    """计算字段名与表头单元格的匹配分数。"""

    if not cell_text or not alias_text:
        return 0

    excluded_words = COLUMN_EXCLUDES.get(field_name, [])
    if any(word in cell_text for word in excluded_words):
        return 0

    if cell_text == alias_text:
        return 1000 + len(alias_text)
    if cell_text.startswith(alias_text) or cell_text.endswith(alias_text):
        return 700 + len(alias_text)
    if alias_text in cell_text:
        return 600 + len(alias_text)
    if len(cell_text) >= 2 and cell_text in alias_text:
        return 500 + len(cell_text)

    return 0


def build_column_map(header_cells: Sequence[Any]) -> ColumnMap:
    """根据实际表头返回统一字段名到列索引的映射。"""

    normalized_cells = [normalize_text(cell) for cell in header_cells]
    candidates: list[tuple[int, int, int, str, int]] = []

    for field_name, aliases in COLUMN_ALIASES.items():
        for column_index, cell_text in enumerate(normalized_cells):
            for alias in aliases:
                alias_text = normalize_text(alias)
                score = field_match_score(field_name, cell_text, alias_text)
                if score:
                    candidates.append(
                        (
                            score,
                            len(alias_text),
                            -column_index,
                            field_name,
                            column_index,
                        )
                    )

    column_map: ColumnMap = {}
    used_columns: set[int] = set()

    for _, _, _, field_name, column_index in sorted(candidates, reverse=True):
        if field_name in column_map or column_index in used_columns:
            continue
        column_map[field_name] = column_index
        used_columns.add(column_index)

    return column_map


def find_header_row(
    raw_frame: pd.DataFrame,
    max_scan_rows: int = HEADER_SCAN_ROWS,
) -> int:
    """在前几行中寻找最像表头的行，找不到时返回 -1。"""

    best_row = -1
    best_score = 0
    scan_limit = min(max_scan_rows, len(raw_frame))

    for row_index in range(scan_limit):
        column_map = build_column_map(raw_frame.iloc[row_index].tolist())
        required_hits = sum(
            1 for column_name in REQUIRED_COLUMNS if column_name in column_map
        )
        score = required_hits * 100 + len(column_map)

        if score > best_score:
            best_row = row_index
            best_score = score

    minimum_score = len(REQUIRED_COLUMNS) * 100
    return best_row if best_score >= minimum_score else -1
