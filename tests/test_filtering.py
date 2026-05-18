from __future__ import annotations

import unittest
import os
import sqlite3
from tempfile import TemporaryDirectory
from pathlib import Path

import pandas as pd

from cotton_filter_app.processor import filter_file, process_sheet, process_sheet_result
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

    def test_score_range_can_apply_numeric_field_without_alias(self) -> None:
        repository = RuleRepository()
        repository.create_data_rule(
            {
                "field_name": "马值",
                "rule_type": "score_range",
                "max_value": 4.2,
                "score_delta": 25,
                "enabled": True,
            }
        )
        rule_set = repository.load_ruleset()

        self.assertEqual(score_record({"马值": "4.1(A)"}, rule_set=rule_set), 25)
        self.assertEqual(score_record({"马值": "4.8(A)"}, rule_set=rule_set), 0)

    def test_batch_and_warehouse_rules_are_not_maintained(self) -> None:
        repository = RuleRepository()
        rule_set = repository.load_ruleset()

        self.assertFalse(
            [
                rule
                for rule in rule_set.enabled_column_rules()
                if rule.field_name in {"批号", "仓库"}
            ]
        )

        with self.assertRaisesRegex(ValueError, "该字段不再维护列名规则"):
            repository.create_column_rule(
                {"field_name": "仓库", "alias": "存放仓库", "enabled": True}
            )

        with self.assertRaisesRegex(ValueError, "该字段不再维护数据规则"):
            repository.create_data_rule(
                {
                    "field_name": "批号",
                    "rule_type": "keyword_filter",
                    "match_value": "A",
                }
            )

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

    def test_numeric_interval_rules_without_applicable_value_are_kept(self) -> None:
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

        self.assertTrue(
            [rule for rule in rules if rule.rule_name == "旧无适用值评分"]
        )

    def test_range_rule_requires_alias_output_value(self) -> None:
        repository = RuleRepository()
        repository.create_data_rule(
            {
                "field_name": "马值",
                "rule_type": "score_range",
                "max_value": 4.2,
                "score_delta": 25,
            }
        )

        with self.assertRaisesRegex(ValueError, "只有颜色级支持值别名"):
            repository.create_data_rule(
                {
                    "field_name": "马值",
                    "rule_type": "value_alias",
                    "match_value": "A",
                    "output_value": "A",
                }
            )

        with self.assertRaisesRegex(ValueError, "区间规则必须选择适用值"):
            repository.create_data_rule(
                {
                    "field_name": "颜色级",
                    "rule_type": "score_range",
                    "max_value": 4.2,
                    "score_delta": 25,
                }
            )

        with self.assertRaisesRegex(ValueError, "适用值必须来自当前字段的值别名输出值"):
            repository.create_data_rule(
                {
                    "field_name": "颜色级",
                    "rule_type": "score_range",
                    "match_value": "不存在",
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
                "field_name": "颜色级",
                "rule_type": "keyword_filter",
                "match_value": "白棉3级",
                "enabled": True,
            }
        )
        raw_frame = pd.DataFrame(
            [
                ["批号", "基差", "长度", "马值", "颜色级"],
                ["A004", 350, 29.5, 4.1, "31"],
                ["A005", 350, 29.5, 4.1, "41"],
            ]
        )

        result = process_sheet(raw_frame)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["颜色级"].tolist(), ["白棉3级"])

    def test_multiple_filter_rules_must_all_match(self) -> None:
        repository = RuleRepository()
        repository.create_data_rule(
            {
                "field_name": "颜色级",
                "rule_type": "keyword_filter",
                "match_value": "白棉3级",
                "enabled": True,
            }
        )
        repository.create_data_rule(
            {
                "field_name": "马值",
                "rule_type": "filter_range",
                "min_value": 4.0,
                "max_value": 4.2,
                "enabled": True,
            }
        )
        raw_frame = pd.DataFrame(
            [
                ["批号", "基差", "长度", "马值", "颜色级"],
                ["A006", 350, 29.5, "4.1(A)", "31"],
                ["A007", 350, 29.5, "4.8(A)", "31"],
                ["A008", 350, 29.5, "4.1(A)", "41"],
            ]
        )

        result = process_sheet(raw_frame)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["颜色级"].tolist(), ["白棉3级"])

    def test_same_field_filter_ranges_are_combined_as_or_per_grade(self) -> None:
        repository = RuleRepository()
        for grade, low in (("白棉1级", 60), ("白棉2级", 60), ("白棉3级", 80)):
            repository.create_data_rule(
                {
                    "field_name": "颜色级",
                    "rule_type": "filter_range",
                    "match_value": grade,
                    "min_value": low,
                    "max_value": 100,
                    "enabled": True,
                }
            )
        raw_frame = pd.DataFrame(
            [
                ["批号", "基差", "长度", "马值", "颜色级"],
                ["K0", 350, 29.5, 4.1, "21:2.2%，31:90.7%，41:2.1%"],
                ["K1", 350, 29.5, 4.1, "白棉2级:2.2%，白棉3级:95.7%"],
                ["K2", 350, 29.5, 4.1, "白棉1级:5.4%，白棉2级:94.1%，白棉3级:0.5%"],
                ["K3", 350, 29.5, 4.1, "白棉2级:1.6%，白棉3级:68.8%"],
            ]
        )

        result = process_sheet(raw_frame)

        self.assertIsNotNone(result)
        assert result is not None
        # K0: 31 是 白棉3级 的值别名，31:90.7 命中 白棉3级>=80。
        # K1: 白棉3级 95.7>=80 命中；K2: 白棉2级 94.1>=60 命中；
        # K3: 白棉2级 1.6<60 且 白棉3级 68.8<80 → 不命中（按本级别比例判定）。
        self.assertEqual(len(result), 3)
        self.assertIn("31:90.7", result.iloc[0]["颜色级"])
        self.assertIn("白棉3级:95.7", result.iloc[1]["颜色级"])
        self.assertIn("白棉2级:94.1", result.iloc[2]["颜色级"])

    def test_filter_file_writes_result_and_issue_sheets_with_original_columns(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "resource.xlsx"
            output = root / "result.xlsx"
            frame = pd.DataFrame(
                [
                    ["批号", "基差", "长度", "马值", "颜色级", "未配置列"],
                    ["A009", 350, 29.5, "4.1(A)", "31", "原始备注"],
                    ["A010", 350, 29.5, "4.1(Z)", "未知色", "异常备注"],
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
            self.assertIn("数据规则未覆盖", issue_frame["异常类型"].tolist())
            self.assertIn("未知色", issue_frame["原值"].fillna("").tolist())
            self.assertNotIn("列名未覆盖", issue_frame["异常类型"].tolist())
            self.assertNotIn("未配置列", issue_frame["原列名"].fillna("").tolist())

    def test_unmapped_column_that_looks_like_known_alias_is_reported(self) -> None:
        raw_frame = pd.DataFrame(
            [
                ["批号", "基差", "长度", "马值", "颜色级1", "未配置列"],
                ["A011", 350, 29.5, 4.1, "白棉3级", "原始备注"],
            ]
        )

        result = process_sheet_result(raw_frame)

        issue_frame = result.issue_frame
        self.assertIn("列名未覆盖", issue_frame["异常类型"].tolist())
        self.assertTrue(
            any("颜色级1" in column for column in issue_frame["原列名"].fillna(""))
        )
        self.assertNotIn("未配置列", issue_frame["原列名"].fillna("").tolist())

    def test_unique_output_path_starts_at_one_and_skips_taken(self) -> None:
        from cotton_filter_app.file_utils import unique_output_path

        with TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            src = Path("/somewhere/资源表.xlsx")

            first = unique_output_path(out_dir, src)
            self.assertEqual(first.name, "资源表.xlsx")

            first.touch()
            second = unique_output_path(out_dir, src)
            self.assertEqual(second.name, "资源表_1.xlsx")

            taken = {first, out_dir / "资源表_1.xlsx"}
            third = unique_output_path(out_dir, src, taken=taken)
            self.assertEqual(third.name, "资源表_2.xlsx")

    def test_filter_file_writes_empty_workbook_when_no_rows_are_kept(self) -> None:
        repository = RuleRepository()
        repository.create_data_rule(
            {
                "field_name": "马值",
                "rule_type": "filter_range",
                "min_value": 5,
                "enabled": True,
            }
        )

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "resource.xlsx"
            output = root / "result.xlsx"
            pd.DataFrame(
                [
                    ["批号", "基差", "长度", "马值"],
                    ["A001", 350, 29.5, "4.1(A)"],
                ]
            ).to_excel(source, index=False, header=False)

            kept = filter_file(source, output)

            self.assertEqual(kept, 0)
            self.assertTrue(output.exists())
            workbook = pd.read_excel(output, sheet_name=None)
            self.assertEqual(len(workbook["筛选结果"]), 0)
            self.assertEqual(len(workbook["识别异常"]), 0)

    def test_locked_output_file_falls_back_to_next_name(self) -> None:
        from cotton_filter_app import file_utils

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "resource.xlsx"
            out_dir = root / "out"
            pd.DataFrame(
                [
                    ["批号", "基差", "长度", "马值"],
                    ["A001", 350, 29.5, 4.1],
                ]
            ).to_excel(source, index=False, header=False)

            real_filter_file = file_utils.filter_file
            attempts: list[str] = []

            def flaky_filter_file(src, dst, log=None):
                attempts.append(dst.name)
                if len(attempts) == 1:
                    raise PermissionError(f"locked: {dst.name}")
                return real_filter_file(src, dst, log=log)

            file_utils.filter_file = flaky_filter_file
            try:
                results = file_utils.filter_files([source], out_dir)
            finally:
                file_utils.filter_file = real_filter_file

            self.assertIsNone(results[0].error)
            self.assertIsNotNone(results[0].out)
            assert results[0].out is not None
            self.assertEqual(results[0].out.name, "resource_1.xlsx")
            self.assertEqual(attempts, ["resource.xlsx", "resource_1.xlsx"])


if __name__ == "__main__":
    unittest.main()
