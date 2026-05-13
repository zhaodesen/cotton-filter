"""Cotton batch scoring rules."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd

from .models import Record


NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
PERCENT_RE = re.compile(r"([-+]?\d+(?:\.\d+)?)\s*[%％]")
COLOR_RATIO_RE = re.compile(r"[:：]\s*([-+]?\d+(?:\.\d+)?)\s*(?:[%％])?")
COLOR_GRADE_RE = re.compile(
    r"(?:白棉|淡点污棉|淡黄染棉|黄染棉)?[一二三四五12345]级"
)
COLOR_GRADE_CODE_RE = re.compile(
    r"(?<!\d)(?:11|21|31|41|51|12|22|32|42|52|13|23|33|43|53)(?!\d)"
)
KNOWN_COLOR_GRADE_CODES = {
    11,
    12,
    13,
    21,
    22,
    23,
    31,
    32,
    33,
    41,
    42,
    43,
    51,
    52,
    53,
}


def parse_float(value: Any, default: float = 0.0) -> float:
    """把 Excel 单元格值转为浮点数，失败时返回默认值。"""

    if value is None or pd.isna(value):
        return default

    if isinstance(value, (int, float)):
        return float(value)

    text = unicodedata.normalize("NFKC", str(value)).strip().replace(",", "")
    if not text:
        return default

    try:
        return float(text)
    except (TypeError, ValueError):
        match = NUMBER_RE.search(text)
        return float(match.group()) if match else default


def extract_max_color_percent(value: Any) -> float:
    """从颜色级文本中提取最大的百分比。"""

    if value is None or pd.isna(value):
        return 0.0

    if isinstance(value, (int, float)):
        numeric_value = float(value)
        if numeric_value.is_integer() and int(numeric_value) in KNOWN_COLOR_GRADE_CODES:
            return 100.0
        if numeric_value.is_integer() and 1 <= int(numeric_value) <= 5:
            return 100.0
        return numeric_value if 0 <= numeric_value <= 100 else 0.0

    text = unicodedata.normalize("NFKC", str(value)).strip()
    if not text or text in {"-", "--", "—", "无"}:
        return 0.0

    values = [
        float(match)
        for match in [*PERCENT_RE.findall(text), *COLOR_RATIO_RE.findall(text)]
    ]
    if values:
        return max(values)

    if COLOR_GRADE_RE.search(text) or COLOR_GRADE_CODE_RE.search(text):
        return 100.0

    return 0.0


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
