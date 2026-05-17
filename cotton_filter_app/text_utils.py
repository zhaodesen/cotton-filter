"""Text normalization helpers shared by rule matching code."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


HEADER_PUNCTUATION_RE = re.compile(r"[\s\u3000]+")
HEADER_SYMBOL_RE = re.compile(r"[()（）【】\[\]{}<>《》:：/\\_\-—%％]+")


def normalize_text(value: Any) -> str:
    """标准化表头和规则文本，用于精确匹配。"""

    if value is None:
        return ""

    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    text = HEADER_PUNCTUATION_RE.sub("", text)
    return HEADER_SYMBOL_RE.sub("", text)
