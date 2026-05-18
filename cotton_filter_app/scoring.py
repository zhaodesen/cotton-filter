"""Cotton batch scoring rules."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd

from .models import Record
from .rules import DataRule, RuleSet, load_ruleset, matches_range
from .text_utils import normalize_text


NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
PERCENT_RE = re.compile(r"([-+]?\d+(?:\.\d+)?)\s*[%％]")
COLOR_RATIO_RE = re.compile(r"[:：]\s*([-+]?\d+(?:\.\d+)?)\s*(?:[%％])?")
COLOR_SEGMENT_SEPARATORS = r",，、;；\s"


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


def color_aliases_for_target(target: str, rule_set: RuleSet) -> list[str]:
    """返回某个标准颜色级对应的所有匹配写法。"""

    target_output = rule_set.value_alias_output("颜色级", target) or target
    target_output_key = normalize_text(target_output)
    aliases = [target, target_output]

    for rule in rule_set.enabled_data_rules():
        if rule.rule_type != "value_alias" or rule.field_name != "颜色级":
            continue
        output_value = rule.output_value or rule.match_value
        if normalize_text(output_value) == target_output_key:
            aliases.extend([rule.match_value, output_value])

    seen: set[str] = set()
    unique_aliases: list[str] = []
    for alias in aliases:
        alias_text = unicodedata.normalize("NFKC", str(alias)).strip()
        alias_key = normalize_text(alias_text)
        if not alias_key or alias_key in seen:
            continue
        seen.add(alias_key)
        unique_aliases.append(alias_text)

    return sorted(unique_aliases, key=len, reverse=True)


def extract_labeled_color_percent(text: str, label: str) -> float | None:
    """从组合颜色级文本中提取指定标签后的百分比。"""

    pattern = (
        rf"(?:^|[{COLOR_SEGMENT_SEPARATORS}])\s*"
        + re.escape(label)
        + r"\s*[:：]\s*([-+]?\d+(?:\.\d+)?)\s*[%％]?"
    )
    match = re.search(pattern, text)
    return float(match.group(1)) if match else None


def extract_color_percent(
    value: Any,
    rule: DataRule,
    rule_set: RuleSet | None = None,
) -> float:
    """提取颜色级文本中规则适用级别(如“白棉3级”)的百分比。

    规则没有指定适用值时回退到最大百分比；指定了适用值时只看该级别的占比，
    避免用其它级别的比例去判定本级别区间。
    """

    active_rule_set = rule_set or load_ruleset()
    target = (rule.match_value or "").strip()
    if not target:
        return extract_max_color_percent(value, active_rule_set)

    if value is None or pd.isna(value):
        return 0.0

    if isinstance(value, (int, float)):
        numeric_value = float(value)
        if not numeric_value.is_integer():
            return numeric_value if 0 <= numeric_value <= 100 else 0.0
        text = str(int(numeric_value))
    else:
        text = unicodedata.normalize("NFKC", str(value)).strip()

    if not text or text in {"-", "--", "—", "无"}:
        return float("nan")

    for alias in color_aliases_for_target(target, active_rule_set):
        percent = extract_labeled_color_percent(text, alias)
        if percent is not None:
            return percent

    target_output = active_rule_set.value_alias_output("颜色级", target)
    cell_output = active_rule_set.value_alias_output("颜色级", text)
    if cell_output is not None and cell_output == (target_output or target):
        return 100.0
    if normalize_text(text) == normalize_text(target):
        return 100.0
    return float("nan")


def score_record(record: Record, rule_set: RuleSet | None = None) -> int:
    """按当前业务规则计算单条棉花资源得分。"""

    active_rule_set = rule_set or load_ruleset()
    score = 0

    for rule in active_rule_set.score_rules():
        raw_value = record.get(rule.field_name)
        if rule.field_name == "颜色级":
            value = extract_color_percent(raw_value, rule, active_rule_set)
        else:
            if not active_rule_set.rule_matches_value(rule, raw_value):
                continue
            value = parse_float(raw_value)
        if pd.isna(value):
            continue
        if matches_range(value, rule):
            score += rule.score_delta or 0

    return score
