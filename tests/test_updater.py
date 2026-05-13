from __future__ import annotations

import unittest

from cotton_filter_app.updater import find_release_commit


class UpdaterTest(unittest.TestCase):
    def test_find_release_commit_reads_github_release_body(self) -> None:
        self.assertEqual(
            find_release_commit(
                "Built automatically from commit "
                "324e183a6e917e9612657c5ce3744ff3aba3acee."
            ),
            "324e183a6e917e9612657c5ce3744ff3aba3acee",
        )

    def test_find_release_commit_returns_none_without_commit(self) -> None:
        self.assertIsNone(find_release_commit("cotton-filter latest"))


if __name__ == "__main__":
    unittest.main()
