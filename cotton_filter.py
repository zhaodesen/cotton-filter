"""GUI entry point for cotton-filter."""

from __future__ import annotations

from cotton_filter_app.file_utils import filter_files
from cotton_filter_app.gui import run_gui
from cotton_filter_app.processor import filter_file, process_sheet


def main() -> int:
    """Start the GUI application."""

    return run_gui()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"\n[错误] {error}")
        raise SystemExit(1)
