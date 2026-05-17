"""SQLite-backed rule repository for cotton-filter."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import APP_NAME
from .text_utils import normalize_text


COLUMN_RULE_TABLE = "column_rules"
DATA_RULE_TABLE = "data_rules"
METADATA_TABLE = "rule_metadata"
RULE_DB_ENV = "COTTON_FILTER_RULE_DB"
DEFAULT_DB_NAME = "rules.sqlite3"
DATA_RULE_TYPES = {"value_alias", "score_range", "filter_range"}
DEFAULT_SEEDED_KEY = "default_rules_seeded"
DEFAULT_REQUIRED_FIELDS = ("基差", "长度", "马值")
DEFAULT_OUTPUT_FIELDS = (
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


@dataclass(frozen=True)
class ColumnRule:
    """列名规则：把 Excel 表头别名映射到统一字段名。"""

    id: int | None
    field_name: str
    alias: str
    alias_key: str
    enabled: bool = True
    sort_order: int = 0
    notes: str = ""


@dataclass(frozen=True)
class DataRule:
    """数据规则：描述单元格值别名、评分区间或最终过滤区间。"""

    id: int | None
    field_name: str
    rule_name: str
    rule_type: str
    match_value: str = ""
    match_key: str = ""
    min_value: float | None = None
    max_value: float | None = None
    min_inclusive: bool = True
    max_inclusive: bool = True
    score_delta: int | None = None
    output_value: str = ""
    enabled: bool = True
    sort_order: int = 0
    notes: str = ""


@dataclass(frozen=True)
class RuleSet:
    """处理 Excel 时使用的一份规则快照。"""

    column_rules: tuple[ColumnRule, ...]
    data_rules: tuple[DataRule, ...]
    required_fields: tuple[str, ...] = DEFAULT_REQUIRED_FIELDS
    output_fields: tuple[str, ...] = DEFAULT_OUTPUT_FIELDS

    def enabled_column_rules(self) -> tuple[ColumnRule, ...]:
        return tuple(rule for rule in self.column_rules if rule.enabled)

    def enabled_data_rules(self) -> tuple[DataRule, ...]:
        return tuple(rule for rule in self.data_rules if rule.enabled)

    def column_candidates(self, cell_value: Any) -> list[ColumnRule]:
        cell_key = normalize_text(cell_value)
        if not cell_key:
            return []

        matches = [
            rule
            for rule in self.enabled_column_rules()
            if rule.alias_key == cell_key
        ]
        return sorted(matches, key=lambda rule: (rule.sort_order, rule.id or 0))

    def is_value_alias(self, field_name: str, value: Any) -> bool:
        value_key = normalize_text(value)
        if not value_key:
            return False

        return any(
            rule.rule_type == "value_alias"
            and rule.field_name == field_name
            and rule.match_key == value_key
            for rule in self.enabled_data_rules()
        )

    def score_rules(self) -> tuple[DataRule, ...]:
        return tuple(
            rule
            for rule in self.enabled_data_rules()
            if rule.rule_type == "score_range" and rule.score_delta is not None
        )

    def filter_rules(self) -> tuple[DataRule, ...]:
        return tuple(
            rule
            for rule in self.enabled_data_rules()
            if rule.rule_type == "filter_range"
        )


def default_rule_db_path() -> Path:
    """返回当前系统下可写的本地规则库路径。"""

    explicit_path = os.environ.get(RULE_DB_ENV)
    if explicit_path:
        return Path(explicit_path).expanduser()

    if os.name == "nt":
        base_dir = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys_platform() == "darwin":
        base_dir = Path.home() / "Library" / "Application Support"
    else:
        base_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    return base_dir / APP_NAME / DEFAULT_DB_NAME


def sys_platform() -> str:
    """隔离平台读取，便于测试时通过环境变量指定库路径。"""

    import sys

    return sys.platform


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_column_rules() -> list[ColumnRule]:
    """把旧版硬编码列名别名作为初始数据库规则。"""

    aliases: dict[str, list[str]] = {
        "基差": ["基差", "销售基差", "销售基差/一口价", "销售\n基差/一口价"],
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
        "强力": [
            "强力",
            "比强",
            "强度",
            "断裂比强度",
            "断裂比强度(cN/tex)",
            "断裂比\n强度(cN/tex)",
        ],
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

    rules: list[ColumnRule] = []
    order = 0
    for field_name, field_aliases in aliases.items():
        for alias in field_aliases:
            rules.append(
                ColumnRule(
                    id=None,
                    field_name=field_name,
                    alias=alias,
                    alias_key=normalize_text(alias),
                    sort_order=order,
                )
            )
            order += 1
    return rules


def default_data_rules() -> list[DataRule]:
    """把旧版硬编码数据识别、评分和筛选阈值作为初始数据库规则。"""

    rules: list[DataRule] = []
    order = 0

    color_aliases = [str(code) for code in range(1, 6)]
    color_aliases.extend(
        str(code)
        for code in (
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
        )
    )
    prefixes = ("", "白棉", "淡点污棉", "淡黄染棉", "黄染棉")
    grade_labels = (("一", "1"), ("二", "2"), ("三", "3"), ("四", "4"), ("五", "5"))
    for prefix in prefixes:
        for chinese_grade, number_grade in grade_labels:
            color_aliases.append(f"{prefix}{chinese_grade}级")
            color_aliases.append(f"{prefix}{number_grade}级")

    seen_aliases: set[str] = set()
    for alias in color_aliases:
        alias_key = normalize_text(alias)
        if alias_key in seen_aliases:
            continue
        seen_aliases.add(alias_key)
        rules.append(
            DataRule(
                id=None,
                field_name="颜色级",
                rule_name=f"颜色级值 {alias}",
                rule_type="value_alias",
                match_value=alias,
                match_key=alias_key,
                output_value=alias,
                sort_order=order,
                notes="匹配后按颜色级直接品级处理为 100%",
            )
        )
        order += 1

    score_rules = [
        DataRule(None, "颜色级", "颜色级主体占比 >= 80 加 100", "score_range", min_value=80, score_delta=100),
        DataRule(None, "长度", "长度 > 30 加 400", "score_range", min_value=30, min_inclusive=False, score_delta=400),
        DataRule(None, "长度", "长度 29 到 30 加 150", "score_range", min_value=29, max_value=30, score_delta=150),
        DataRule(None, "马值", "马值 < 4.2 加 100", "score_range", max_value=4.2, max_inclusive=False, score_delta=100),
        DataRule(None, "马值", "马值 > 5 减 100", "score_range", min_value=5, min_inclusive=False, score_delta=-100),
        DataRule(None, "整齐度", "整齐度 > 83 加 200", "score_range", min_value=83, min_inclusive=False, score_delta=200),
        DataRule(None, "强力", "强力 > 31 加 250", "score_range", min_value=31, min_inclusive=False, score_delta=250),
        DataRule(None, "强力", "强力 29 到 31 加 150", "score_range", min_value=29, max_value=31, score_delta=150),
        DataRule(None, "与基差差距", "与基差差距 -100 到 100 保留", "filter_range", min_value=-100, max_value=100),
    ]
    for rule in score_rules:
        rules.append(
            DataRule(
                id=None,
                field_name=rule.field_name,
                rule_name=rule.rule_name,
                rule_type=rule.rule_type,
                min_value=rule.min_value,
                max_value=rule.max_value,
                min_inclusive=rule.min_inclusive,
                max_inclusive=rule.max_inclusive,
                score_delta=rule.score_delta,
                sort_order=order,
            )
        )
        order += 1

    return rules


class RuleRepository:
    """负责本地 SQLite 规则库的初始化、读取和维护。"""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or default_rule_db_path()

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with closing(self.connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS column_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    field_name TEXT NOT NULL,
                    alias TEXT NOT NULL,
                    alias_key TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(field_name, alias_key)
                );

                CREATE TABLE IF NOT EXISTS data_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    field_name TEXT NOT NULL,
                    rule_name TEXT NOT NULL,
                    rule_type TEXT NOT NULL,
                    match_value TEXT NOT NULL DEFAULT '',
                    match_key TEXT NOT NULL DEFAULT '',
                    min_value REAL,
                    max_value REAL,
                    min_inclusive INTEGER NOT NULL DEFAULT 1,
                    max_inclusive INTEGER NOT NULL DEFAULT 1,
                    score_delta INTEGER,
                    output_value TEXT NOT NULL DEFAULT '',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_data_value_alias
                    ON data_rules(field_name, rule_type, match_key)
                    WHERE rule_type = 'value_alias';

                CREATE TABLE IF NOT EXISTS rule_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            connection.commit()
            self.seed_defaults(connection, force=False)

    def seed_defaults(
        self,
        connection: sqlite3.Connection | None = None,
        force: bool = False,
    ) -> None:
        owns_connection = connection is None
        active_connection = connection or self.connect()
        try:
            if not force:
                if self._default_seeded(active_connection):
                    return
                if not self._is_empty(active_connection):
                    self._mark_default_seeded(active_connection)
                    active_connection.commit()
                    return
            for rule in default_column_rules():
                self._insert_column_rule(active_connection, rule, ignore_duplicates=True)
            for rule in default_data_rules():
                self._insert_data_rule(active_connection, rule, ignore_duplicates=True)
            self._mark_default_seeded(active_connection)
            active_connection.commit()
        finally:
            if owns_connection:
                active_connection.close()

    def load_ruleset(self) -> RuleSet:
        self.initialize()
        return RuleSet(
            column_rules=tuple(self.list_column_rules()),
            data_rules=tuple(self.list_data_rules()),
        )

    def list_column_rules(self) -> list[ColumnRule]:
        self.initialize()
        with closing(self.connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT id, field_name, alias, alias_key, enabled, sort_order, notes
                FROM {COLUMN_RULE_TABLE}
                ORDER BY sort_order, field_name, alias
                """
            ).fetchall()
        return [self._row_to_column_rule(row) for row in rows]

    def list_data_rules(self) -> list[DataRule]:
        self.initialize()
        with closing(self.connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT id, field_name, rule_name, rule_type, match_value, match_key,
                       min_value, max_value, min_inclusive, max_inclusive,
                       score_delta, output_value, enabled, sort_order, notes
                FROM {DATA_RULE_TABLE}
                ORDER BY sort_order, field_name, rule_name
                """
            ).fetchall()
        return [self._row_to_data_rule(row) for row in rows]

    def create_column_rule(self, payload: dict[str, Any]) -> ColumnRule:
        self.initialize()
        rule = self._column_rule_from_payload(payload)
        with closing(self.connect()) as connection:
            rule_id = self._insert_column_rule(connection, rule, ignore_duplicates=False)
            connection.commit()
        return self.get_column_rule(rule_id)

    def delete_column_rule(self, rule_id: int) -> None:
        self.initialize()
        with closing(self.connect()) as connection:
            cursor = connection.execute(
                f"DELETE FROM {COLUMN_RULE_TABLE} WHERE id = ?",
                (rule_id,),
            )
            connection.commit()
            if cursor.rowcount == 0:
                raise KeyError(rule_id)

    def get_column_rule(self, rule_id: int) -> ColumnRule:
        with closing(self.connect()) as connection:
            row = connection.execute(
                f"""
                SELECT id, field_name, alias, alias_key, enabled, sort_order, notes
                FROM {COLUMN_RULE_TABLE}
                WHERE id = ?
                """,
                (rule_id,),
            ).fetchone()
        if row is None:
            raise KeyError(rule_id)
        return self._row_to_column_rule(row)

    def create_data_rule(self, payload: dict[str, Any]) -> DataRule:
        self.initialize()
        rule = self._data_rule_from_payload(payload)
        with closing(self.connect()) as connection:
            rule_id = self._insert_data_rule(connection, rule, ignore_duplicates=False)
            connection.commit()
        return self.get_data_rule(rule_id)

    def delete_data_rule(self, rule_id: int) -> None:
        self.initialize()
        with closing(self.connect()) as connection:
            cursor = connection.execute(
                f"DELETE FROM {DATA_RULE_TABLE} WHERE id = ?",
                (rule_id,),
            )
            connection.commit()
            if cursor.rowcount == 0:
                raise KeyError(rule_id)

    def get_data_rule(self, rule_id: int) -> DataRule:
        with closing(self.connect()) as connection:
            row = connection.execute(
                f"""
                SELECT id, field_name, rule_name, rule_type, match_value, match_key,
                       min_value, max_value, min_inclusive, max_inclusive,
                       score_delta, output_value, enabled, sort_order, notes
                FROM {DATA_RULE_TABLE}
                WHERE id = ?
                """,
                (rule_id,),
            ).fetchone()
        if row is None:
            raise KeyError(rule_id)
        return self._row_to_data_rule(row)

    def _insert_column_rule(
        self,
        connection: sqlite3.Connection,
        rule: ColumnRule,
        ignore_duplicates: bool,
    ) -> int:
        now = utc_now()
        statement = "INSERT OR IGNORE" if ignore_duplicates else "INSERT"
        try:
            cursor = connection.execute(
                f"""
                {statement} INTO {COLUMN_RULE_TABLE}
                (field_name, alias, alias_key, enabled, sort_order, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule.field_name,
                    rule.alias,
                    rule.alias_key,
                    int(rule.enabled),
                    rule.sort_order,
                    rule.notes,
                    now,
                    now,
                ),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("列名规则已存在") from error
        return int(cursor.lastrowid)

    @staticmethod
    def _is_empty(connection: sqlite3.Connection) -> bool:
        column_count = connection.execute(
            f"SELECT COUNT(*) FROM {COLUMN_RULE_TABLE}"
        ).fetchone()[0]
        data_count = connection.execute(
            f"SELECT COUNT(*) FROM {DATA_RULE_TABLE}"
        ).fetchone()[0]
        return int(column_count) == 0 and int(data_count) == 0

    @staticmethod
    def _default_seeded(connection: sqlite3.Connection) -> bool:
        row = connection.execute(
            f"SELECT value FROM {METADATA_TABLE} WHERE key = ?",
            (DEFAULT_SEEDED_KEY,),
        ).fetchone()
        return row is not None and str(row["value"]) == "1"

    @staticmethod
    def _mark_default_seeded(connection: sqlite3.Connection) -> None:
        connection.execute(
            f"""
            INSERT INTO {METADATA_TABLE} (key, value, updated_at)
            VALUES (?, '1', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (DEFAULT_SEEDED_KEY, utc_now()),
        )

    def _insert_data_rule(
        self,
        connection: sqlite3.Connection,
        rule: DataRule,
        ignore_duplicates: bool,
    ) -> int:
        now = utc_now()
        statement = "INSERT OR IGNORE" if ignore_duplicates else "INSERT"
        try:
            cursor = connection.execute(
                f"""
                {statement} INTO {DATA_RULE_TABLE}
                (field_name, rule_name, rule_type, match_value, match_key,
                 min_value, max_value, min_inclusive, max_inclusive, score_delta,
                 output_value, enabled, sort_order, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._data_rule_values(rule) + (now, now),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("数据规则已存在") from error
        return int(cursor.lastrowid)

    def _column_rule_from_payload(self, payload: dict[str, Any]) -> ColumnRule:
        field_name = str(payload.get("field_name") or "").strip()
        alias = str(payload.get("alias") or "").strip()
        if not field_name:
            raise ValueError("标准字段不能为空")
        if not alias:
            raise ValueError("列名别名不能为空")

        return ColumnRule(
            id=None,
            field_name=field_name,
            alias=alias,
            alias_key=normalize_text(alias),
            enabled=bool(payload.get("enabled", True)),
            sort_order=int(payload.get("sort_order") or 0),
            notes=str(payload.get("notes") or "").strip(),
        )

    def _data_rule_from_payload(self, payload: dict[str, Any]) -> DataRule:
        field_name = str(payload.get("field_name") or "").strip()
        rule_name = str(payload.get("rule_name") or "").strip()
        rule_type = str(payload.get("rule_type") or "").strip()
        if not field_name:
            raise ValueError("字段不能为空")
        if not rule_name:
            raise ValueError("规则名称不能为空")
        if rule_type not in DATA_RULE_TYPES:
            raise ValueError("数据规则类型不支持")

        match_value = str(payload.get("match_value") or "").strip()
        min_value = self._optional_float(payload.get("min_value"))
        max_value = self._optional_float(payload.get("max_value"))
        score_delta = self._optional_int(payload.get("score_delta"))
        if rule_type == "value_alias" and not match_value:
            raise ValueError("值别名规则必须填写匹配值")
        if rule_type in {"score_range", "filter_range"} and min_value is None and max_value is None:
            raise ValueError("区间规则至少要填写一个边界")
        if rule_type == "score_range" and score_delta is None:
            raise ValueError("评分区间必须填写加减分")

        return DataRule(
            id=None,
            field_name=field_name,
            rule_name=rule_name,
            rule_type=rule_type,
            match_value=match_value,
            match_key=normalize_text(match_value),
            min_value=min_value,
            max_value=max_value,
            min_inclusive=bool(payload.get("min_inclusive", True)),
            max_inclusive=bool(payload.get("max_inclusive", True)),
            score_delta=score_delta,
            output_value=str(payload.get("output_value") or "").strip(),
            enabled=bool(payload.get("enabled", True)),
            sort_order=int(payload.get("sort_order") or 0),
            notes=str(payload.get("notes") or "").strip(),
        )

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        return float(value)

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        return int(value)

    @staticmethod
    def _row_to_column_rule(row: sqlite3.Row) -> ColumnRule:
        return ColumnRule(
            id=int(row["id"]),
            field_name=str(row["field_name"]),
            alias=str(row["alias"]),
            alias_key=str(row["alias_key"]),
            enabled=bool(row["enabled"]),
            sort_order=int(row["sort_order"]),
            notes=str(row["notes"] or ""),
        )

    @staticmethod
    def _row_to_data_rule(row: sqlite3.Row) -> DataRule:
        return DataRule(
            id=int(row["id"]),
            field_name=str(row["field_name"]),
            rule_name=str(row["rule_name"]),
            rule_type=str(row["rule_type"]),
            match_value=str(row["match_value"] or ""),
            match_key=str(row["match_key"] or ""),
            min_value=row["min_value"],
            max_value=row["max_value"],
            min_inclusive=bool(row["min_inclusive"]),
            max_inclusive=bool(row["max_inclusive"]),
            score_delta=row["score_delta"],
            output_value=str(row["output_value"] or ""),
            enabled=bool(row["enabled"]),
            sort_order=int(row["sort_order"]),
            notes=str(row["notes"] or ""),
        )

    @staticmethod
    def _data_rule_values(rule: DataRule) -> tuple[Any, ...]:
        return (
            rule.field_name,
            rule.rule_name,
            rule.rule_type,
            rule.match_value,
            rule.match_key,
            rule.min_value,
            rule.max_value,
            int(rule.min_inclusive),
            int(rule.max_inclusive),
            rule.score_delta,
            rule.output_value,
            int(rule.enabled),
            rule.sort_order,
            rule.notes,
        )


def load_ruleset() -> RuleSet:
    return RuleRepository().load_ruleset()


def matches_range(value: float, rule: DataRule) -> bool:
    """判断数值是否命中规则区间。"""

    if rule.min_value is not None:
        if rule.min_inclusive and value < rule.min_value:
            return False
        if not rule.min_inclusive and value <= rule.min_value:
            return False
    if rule.max_value is not None:
        if rule.max_inclusive and value > rule.max_value:
            return False
        if not rule.max_inclusive and value >= rule.max_value:
            return False
    return True
