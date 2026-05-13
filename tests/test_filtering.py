from __future__ import annotations

import unittest

import pandas as pd

from cotton_filter_app.processor import process_sheet
from cotton_filter_app.scoring import extract_max_color_percent, parse_float


class FilteringRulesTest(unittest.TestCase):
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
        self.assertEqual(row["得分"], 1050)
        self.assertEqual(row["与基差差距"], -50)
        self.assertIn("白棉3级:95%", row["颜色级"])


if __name__ == "__main__":
    unittest.main()
