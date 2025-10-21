"""Command-line entry point for the AHG LIS Project."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ahg_lis_project.gui import main as gui_main


def _build_subparser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    build_parser = subparsers.add_parser(
        "build",
        help="Create a distributable Windows executable using PyInstaller.",
    )
    build_parser.add_argument(
        "--dist-dir",
        type=Path,
        default=None,
        help="Destination directory for the packaged application (defaults to dist/AHG_LIS_GUI).",
    )
    build_parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Skip removing previous build artefacts before invoking PyInstaller.",
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AHG LIS Project utilities")
    subparsers = parser.add_subparsers(dest="command")
    _build_subparser(subparsers)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.command == "build":
        from ahg_lis_project.build import BuildError, build_executable

        try:
            dist_dir = build_executable(dist_dir=args.dist_dir, clean=not args.no_clean)
        except BuildError as exc:  # pragma: no cover - build failures only visible at runtime
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"Executable written to {dist_dir}")
            return

    gui_main()


if __name__ == "__main__":
    main()
