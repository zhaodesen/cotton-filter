from __future__ import annotations

import unittest
import urllib.error
from unittest import mock

from cotton_filter_app import updater
from cotton_filter_app.updater import get_update_info, normalize_version, validate_digest


class UpdaterTest(unittest.TestCase):
    def test_normalize_version_removes_v_prefix(self) -> None:
        self.assertEqual(normalize_version("v1.2.3"), "1.2.3")

    def test_normalize_version_trims_spaces(self) -> None:
        self.assertEqual(normalize_version("  1.2.3  "), "1.2.3")

    @mock.patch.object(updater, "can_self_update", return_value=True)
    @mock.patch.object(updater, "BUILD_VERSION", "v1.0.0")
    @mock.patch("urllib.request.urlopen")
    def test_get_update_info_reports_inaccessible_latest_release(
        self,
        urlopen: mock.Mock,
        _can_self_update: mock.Mock,
    ) -> None:
        urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.github.com/repos/zhaodesen/cotton-filter/releases/latest",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )

        with self.assertRaisesRegex(RuntimeError, "无法访问 GitHub latest release"):
            get_update_info()

    def test_validate_digest_rejects_mismatched_sha256(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "update.exe"
            file_path.write_bytes(b"not the expected file")

            with self.assertRaisesRegex(RuntimeError, "校验失败"):
                validate_digest(file_path, "sha256:" + "0" * 64)


if __name__ == "__main__":
    unittest.main()
