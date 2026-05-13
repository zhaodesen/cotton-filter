"""Cotton batch scoring rules."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from .models import Record


PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[%％]")


def parse_float(value: Any, default: float = 0.0) -> float:
    """把 Excel 单元格值转为浮点数，失败时返回默认值。"""

    if value is None or pd.isna(value):
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def extract_max_color_percent(value: Any) -> float:
    """从颜色级文本中提取最大的百分比。"""

    if value is None or pd.isna(value):
        return 0.0

    matches = PERCENT_RE.findall(str(value))
    return max((float(match) for match in matches), default=0.0)


def score_record(record: Record) -> int:
    """按当前业务规则计算单条棉花资源得分。"""

    score = 0

    if extract_max_color_percent(record.get("颜色级")) >= 80:
        score += 100

    length = parse_float(record.get("长度"))
    if length > 30:
        score += 400
    elif 29 <= length <= 30:
        score += 150

    micronaire = parse_float(record.get("马值"))
    if micronaire and micronaire < 4.2:
        score += 100
    elif micronaire > 5:
        score -= 100

    if parse_float(record.get("整齐度")) > 83:
        score += 200

    strength = parse_float(record.get("强力"))
    if strength > 31:
        score += 250
    elif 29 <= strength <= 31:
        score += 150

    return score
