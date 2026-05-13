"""Shared configuration for cotton-filter."""

from __future__ import annotations


APP_NAME = "cotton-filter"
RESULT_DIR_NAME = "cotton-filter-results"
EXCEL_SUFFIXES = {".xlsx", ".xls"}

REQUIRED_COLUMNS = ("基差", "长度", "马值")
OUTPUT_COLUMNS = (
    "批号",
    "基差",
    "得分",
    "与基差差距",
    "长度",
    "强力",
    "马值",
    "整齐度",
    "颜色级",
)

HEADER_SCAN_ROWS = 30
MAX_SCORE_GAP = 100

# key 为统一字段名，value 为可能出现的列名。
COLUMN_ALIASES: dict[str, list[str]] = {
    "基差": ["基差"],
    "颜色级": [
        "颜色级",
        "颜色级占比",
        "颜色级比例",
        "颜色级别",
        "颜色级/品级",
        "颜色级品级",
        "色级",
        "品级",
        "品级占比",
        "品级比例",
    ],
    "长度": ["长度", "平均长度", "长度级比例"],
    "强力": ["强力", "比强", "强度", "断裂比强度"],
    "马值": [
        "马值",
        "码值",
        "平均马值",
        "平均码值",
        "马克隆",
        "马克隆值",
        "马克隆值级",
        "mic",
        "mic值",
    ],
    "整齐度": ["整齐度", "长整", "整齐度指数", "长度整齐度", "平均整齐度"],
    "批号": ["批号"],
}

COLUMN_EXCLUDES: dict[str, list[str]] = {
    "长度": ["整齐", "长整", "强", "马", "码", "颜色", "色级", "品级"],
}
