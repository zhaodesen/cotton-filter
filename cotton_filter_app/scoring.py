"""Cotton batch scoring rules."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd

from .models import Record
from .rules import RuleSet, load_ruleset, matches_range


NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
PERCENT_RE = re.compile(r"([-+]?\d+(?:\.\d+)?)\s*[%％]")
COLOR_RATIO_RE = re.compile(r"[:：]\s*([-+]?\d+(?:\.\d+)?)\s*(?:[%％])?")


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


def extract_max_color_percent(
    value: Any,
    rule_set: RuleSet | None = None,
) -> float:
    """从颜色级文本中提取最大的百分比。"""

    active_rule_set = rule_set or load_ruleset()

    if value is None or pd.isna(value):
        return 0.0

    if isinstance(value, (int, float)):
        numeric_value = float(value)
        if numeric_value.is_integer() and active_rule_set.is_value_alias(
            "颜色级",
            str(int(numeric_value)),
        ):
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

    if active_rule_set.is_value_alias("颜色级", text):
        return 100.0

    return 0.0


def score_record(record: Record, rule_set: RuleSet | None = None) -> int:
    """按当前业务规则计算单条棉花资源得分。"""

    active_rule_set = rule_set or load_ruleset()
    score = 0

    for rule in active_rule_set.score_rules():
        raw_value = record.get(rule.field_name)
        if not active_rule_set.rule_matches_value(rule, raw_value):
            continue
        if rule.field_name == "颜色级":
            value = extract_max_color_percent(raw_value, active_rule_set)
        else:
            value = parse_float(raw_value)
        if matches_range(value, rule):
            score += rule.score_delta or 0

    return score
