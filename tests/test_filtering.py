from __future__ import annotations

import unittest
import os
import sqlite3
from tempfile import TemporaryDirectory
from pathlib import Path

import pandas as pd

from cotton_filter_app.processor import filter_file, process_sheet
from cotton_filter_app.scoring import extract_max_color_percent, parse_float, score_record
from cotton_filter_app.rules import (
    RULE_DB_ENV,
    RuleRepository,
    standard_color_grade_value,
)


class FilteringRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.previous_rule_db = os.environ.get(RULE_DB_ENV)
        os.environ[RULE_DB_ENV] = f"{self.temp_dir.name}/rules.sqlite3"

    def tearDown(self) -> None:
        if self.previous_rule_db is None:
            os.environ.pop(RULE_DB_ENV, None)
        else:
            os.environ[RULE_DB_ENV] = self.previous_rule_db
        self.temp_dir.cleanup()

    def test_color_percent_accepts_common_excel_formats(self) -> None:
        self.assertEqual(extract_max_color_percent("31:84.4 21:15.6"), 84.4)
        self.assertEqual(extract_max_color_percent("白棉3级"), 100.0)
        self.assertEqual(extract_max_color_percent("31"), 100.0)
        self.assertEqual(
            extract_max_color_percent("无主体(31:65.1% 21:34.9%)"),
            65.1,
        )
        self.assertEqual(extract_max_color_percent("--"), 0.0)

    def test_parse_float_reads_numbers_inside_text(self) -> None:
        self.assertEqual(parse_float("30.5mm"), 30.5)
        self.assertEqual(parse_float("4.1(A)"), 4.1)
        self.assertEqual(parse_float("打包-1500"), -1500.0)

    def test_color_grade_aliases_have_standard_output_values(self) -> None:
        self.assertEqual(standard_color_grade_value("31"), "白棉3级")
        self.assertEqual(standard_color_grade_value("白棉三级"), "白棉3级")
        self.assertEqual(standard_color_grade_value("白棉3级"), "白棉3级")
        self.assertEqual(standard_color_grade_value("三级棉"), "白棉3级")

        repository = RuleRepository()
        rules = repository.load_ruleset().enabled_data_rules()
        color_rules = {
            rule.match_value: rule.output_value
            for rule in rules
            if rule.field_name == "颜色级" and rule.rule_type == "value_alias"
        }
        self.assertEqual(color_rules["31"], "白棉3级")
        self.assertEqual(color_rules["白棉3级"], "白棉3级")

    def test_process_sheet_supports_grouped_color_columns(self) -> None:
        raw_frame = pd.DataFrame(
            [
                [
                    "序号",
                    "批号",
                    "销售\n基差/一口价",
                    "长度级比例(%)",
                    "断裂比\n强度(cN/tex)",
                    "马克隆值级(%)",
                    "长度整齐度(%)",
                    "颜色级比例(%)",
                    None,
                    None,
                    "毛重",
                ],
                [
                    None,
                    None,
                    None,
                    "平均",
                    "平均值",
                    "平均",
                    "平均值",
                    "白棉\n2级",
                    "白棉\n3级",
                    "白棉\n4级",
                    None,
                ],
                [1, "A001", 1000, 30.5, 31.2, 4.1, 84.2, "--", 95, 5, 42.5],
            ]
        )

        result = process_sheet(raw_frame)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertEqual(row["批号"], "A001")
        self.assertEqual(row["得分"], 0)
        self.assertEqual(row["与基差差距"], 1000)
        self.assertIn("白棉3级:95%", row["颜色级"])

    def test_added_rules_are_used_by_processor(self) -> None:
        repository = RuleRepository()
        repository.create_column_rule(
            {
                "field_name": "马值",
                "alias": "客户马值字段",
                "enabled": True,
            }
        )
        repository.create_data_rule(
            {
                "field_name": "颜色级",
                "rule_type": "value_alias",
                "match_value": "三级棉",
                "enabled": True,
            }
        )
        raw_frame = pd.DataFrame(
            [
                ["批号", "基差", "长度", "客户马值字段", "颜色级"],
                ["A002", 350, 29.5, 4.1, "三级棉"],
            ]
        )

        result = process_sheet(raw_frame)

        self.assertIsNotNone(result)
        assert result is not None
        row = result.iloc[0]
        self.assertEqual(row["马值"], 4.1)
        self.assertEqual(row["颜色级"], "白棉3级")
        self.assertEqual(row["得分"], 0)

    def test_color_grade_alias_is_normalized_in_output(self) -> None:
        raw_frame = pd.DataFrame(
            [
                ["批号", "基差", "长度", "马值", "颜色级"],
                ["A003", 350, 29.5, 4.1, "31"],
            ]
        )

        result = process_sheet(raw_frame)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.iloc[0]["颜色级"], "白棉3级")

    def test_score_range_can_target_specific_value(self) -> None:
        repository = RuleRepository()
        repository.create_data_rule(
            {
                "field_name": "马值",
                "rule_type": "value_alias",
                "match_value": "A",
                "output_value": "A",
                "enabled": True,
            }
        )
        repository.create_data_rule(
            {
                "field_name": "马值",
                "rule_type": "score_range",
                "match_value": "A",
                "max_value": 4.2,
                "score_delta": 25,
                "enabled": True,
            }
        )
        rule_set = repository.load_ruleset()

        self.assertEqual(score_record({"马值": "4.1(A)"}, rule_set=rule_set), 25)
        self.assertEqual(score_record({"马值": "4.1(B)"}, rule_set=rule_set), 0)

    def test_legacy_interval_rules_are_removed_from_defaults(self) -> None:
        repository = RuleRepository()
        rules = repository.load_ruleset().enabled_data_rules()

        self.assertFalse(
            [
                rule
                for rule in rules
                if rule.rule_type in {"score_range", "filter_range"}
                and not rule.match_value
            ]
        )

    def test_legacy_interval_rules_are_removed_from_existing_database(self) -> None:
        repository = RuleRepository()
        repository.initialize()
        with sqlite3.connect(os.environ[RULE_DB_ENV]) as connection:
            connection.execute(
                """
                INSERT INTO data_rules
                (field_name, rule_name, rule_type, match_value, match_key,
                 min_value, max_value, min_inclusive, max_inclusive, score_delta,
                 output_value, enabled, sort_order, notes, created_at, updated_at)
                VALUES ('马值', '旧无适用值评分', 'score_range', '', '',
                        NULL, 4.2, 1, 1, 25, '', 1, 0, '', 'now', 'now')
                """
            )
            connection.commit()

        repository.initialize()
        rules = repository.load_ruleset().enabled_data_rules()

        self.assertFalse(
            [
                rule
                for rule in rules
                if rule.rule_name == "旧无适用值评分"
            ]
        )

    def test_range_rule_requires_alias_output_value(self) -> None:
        repository = RuleRepository()
        with self.assertRaisesRegex(ValueError, "区间规则必须选择适用值"):
            repository.create_data_rule(
                {
                    "field_name": "马值",
                    "rule_type": "score_range",
                    "max_value": 4.2,
                    "score_delta": 25,
                }
            )

        with self.assertRaisesRegex(ValueError, "适用值必须来自当前字段的值别名输出值"):
            repository.create_data_rule(
                {
                    "field_name": "马值",
                    "rule_type": "score_range",
                    "match_value": "A",
                    "max_value": 4.2,
                    "score_delta": 25,
                }
            )

    def test_range_rule_accepts_percent_boundaries(self) -> None:
        repository = RuleRepository()
        repository.create_data_rule(
            {
                "field_name": "颜色级",
                "rule_type": "score_range",
                "match_value": "白棉3级",
                "min_value": "80%",
                "max_value": "95％",
                "score_delta": 25,
            }
        )

        rule = [
            item
            for item in repository.load_ruleset().enabled_data_rules()
            if item.field_name == "颜色级"
            and item.rule_type == "score_range"
            and item.score_delta == 25
        ][0]

        self.assertEqual(rule.min_value, 80.0)
        self.assertEqual(rule.max_value, 95.0)

    def test_keyword_filter_keeps_matching_rows(self) -> None:
        repository = RuleRepository()
        repository.create_data_rule(
            {
                "field_name": "仓库",
                "rule_type": "keyword_filter",
                "match_value": "上海",
                "enabled": True,
            }
        )
        raw_frame = pd.DataFrame(
            [
                ["批号", "基差", "长度", "马值", "仓库"],
                ["A004", 350, 29.5, 4.1, "上海一号库"],
                ["A005", 350, 29.5, 4.1, "青岛库"],
            ]
        )

        result = process_sheet(raw_frame)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["批号"].tolist(), ["A004"])

    def test_multiple_filter_rules_must_all_match(self) -> None:
        repository = RuleRepository()
        repository.create_data_rule(
            {
                "field_name": "仓库",
                "rule_type": "keyword_filter",
                "match_value": "上海",
                "enabled": True,
            }
        )
        repository.create_data_rule(
            {
                "field_name": "马值",
                "rule_type": "value_alias",
                "match_value": "A",
                "output_value": "A",
                "enabled": True,
            }
        )
        repository.create_data_rule(
            {
                "field_name": "马值",
                "rule_type": "filter_range",
                "match_value": "A",
                "min_value": 4.0,
                "max_value": 4.2,
                "enabled": True,
            }
        )
        raw_frame = pd.DataFrame(
            [
                ["批号", "基差", "长度", "马值", "仓库"],
                ["A006", 350, 29.5, "4.1(A)", "上海一号库"],
                ["A007", 350, 29.5, "4.8(A)", "上海一号库"],
                ["A008", 350, 29.5, "4.1(A)", "青岛库"],
            ]
        )

        result = process_sheet(raw_frame)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["批号"].tolist(), ["A006"])

    def test_filter_file_writes_result_and_issue_sheets_with_original_columns(self) -> None:
        repository = RuleRepository()
        repository.create_data_rule(
            {
                "field_name": "马值",
                "rule_type": "value_alias",
                "match_value": "A",
                "output_value": "A",
                "enabled": True,
            }
        )

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "resource.xlsx"
            output = root / "result.xlsx"
            frame = pd.DataFrame(
                [
                    ["批号", "基差", "长度", "马值", "未配置列"],
                    ["A009", 350, 29.5, "4.1(A)", "原始备注"],
                    ["A010", 350, 29.5, "4.1(Z)", "异常备注"],
                ]
            )
            frame.to_excel(source, index=False, header=False)

            kept = filter_file(source, output)

            self.assertEqual(kept, 2)
            workbook = pd.read_excel(output, sheet_name=None)
            self.assertIn("筛选结果", workbook)
            self.assertIn("识别异常", workbook)

            result_frame = workbook["筛选结果"]
            self.assertIn("未配置列", result_frame.columns)
            self.assertIn("得分", result_frame.columns)
            self.assertEqual(result_frame.loc[0, "马值"], "4.1(A)")
            self.assertEqual(result_frame.loc[0, "未配置列"], "原始备注")

            issue_frame = workbook["识别异常"]
            self.assertIn("列名未覆盖", issue_frame["异常类型"].tolist())
            self.assertIn("数据规则未覆盖", issue_frame["异常类型"].tolist())
            self.assertIn("未配置列", issue_frame["原列名"].fillna("").tolist())
            self.assertIn("4.1(Z)", issue_frame["原值"].fillna("").tolist())


if __name__ == "__main__":
    unittest.main()
