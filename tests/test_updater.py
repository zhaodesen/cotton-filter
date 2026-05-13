from __future__ import annotations

import unittest

from cotton_filter_app.updater import normalize_version


class UpdaterTest(unittest.TestCase):
    def test_normalize_version_removes_v_prefix(self) -> None:
        self.assertEqual(normalize_version("v1.2.3"), "1.2.3")

    def test_normalize_version_trims_spaces(self) -> None:
        self.assertEqual(normalize_version("  1.2.3  "), "1.2.3")


if __name__ == "__main__":
    unittest.main()
