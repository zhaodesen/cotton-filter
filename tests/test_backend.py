from __future__ import annotations

import unittest
import os
from tempfile import TemporaryDirectory
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend.server import create_app
from cotton_filter_app.rules import RULE_DB_ENV


class BackendApiTest(unittest.TestCase):
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

    def test_health_reports_ok(self) -> None:
        client = TestClient(create_app())

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_filter_endpoint_reuses_excel_processor(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "resource.xlsx"
            output_dir = root / "results"
            frame = pd.DataFrame(
                [
                    ["批号", "基差", "长度", "强力", "马值", "整齐度", "颜色级"],
                    ["A001", 1000, 30.5, 31.2, 4.1, 84.2, "31"],
                ]
            )
            frame.to_excel(source, index=False, header=False)
            client = TestClient(create_app())

            response = client.post(
                "/api/filter",
                json={"files": [str(source)], "output_dir": str(output_dir)},
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["total_files"], 1)
            self.assertEqual(payload["total_kept"], 1)
            self.assertTrue(Path(payload["results"][0]["out"]).exists())

    def test_rules_api_creates_column_rule(self) -> None:
        client = TestClient(create_app())

        response = client.post(
            "/api/rules/column",
            json={"field_name": "马值", "alias": "客户马值字段", "enabled": True},
        )
        rules_response = client.get("/api/rules")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(rules_response.status_code, 200)
        aliases = {
            rule["alias"]
            for rule in rules_response.json()["column_rules"]
            if rule["field_name"] == "马值"
        }
        self.assertIn("客户马值字段", aliases)


if __name__ == "__main__":
    unittest.main()
