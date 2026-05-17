from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend.server import create_app


class BackendApiTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
