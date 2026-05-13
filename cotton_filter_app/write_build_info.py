"""Write build metadata during CI packaging."""

from __future__ import annotations

import os
from pathlib import Path


def main() -> int:
    """Write the current Git commit into build_info.py."""

    commit = os.environ["BUILD_COMMIT"]
    Path("cotton_filter_app/build_info.py").write_text(
        '"""Build metadata injected by GitHub Actions."""\n\n'
        "from __future__ import annotations\n\n\n"
        f'BUILD_COMMIT = "{commit}"\n',
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
