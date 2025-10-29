"""Command line interface for DeeBee."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from rich.console import Console

from .imdb_client import IMDBClient
from .renamer import DEFAULT_RENAME_FORMAT_KEY, MovieRenamer


LOG_LEVEL_CHOICES = ["critical", "error", "warning", "info", "debug"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DeeBee movie library organizer")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(Path.cwd()),
        help="Directory containing movie files to process",
    )
    parser.add_argument(
        "--execute",
        dest="dry_run",
        action="store_false",
        help="Rename files instead of running in dry-run mode",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of IMDB results to present",
    )
    formats = MovieRenamer.available_formats()
    format_descriptions = ", ".join(f"{spec.key}: {spec.label}" for spec in formats)
    parser.add_argument(
        "--format",
        dest="rename_format",
        choices=[spec.key for spec in formats],
        default=DEFAULT_RENAME_FORMAT_KEY,
        help=f"Filename format to use. Available options: {format_descriptions}",
    )
    parser.add_argument(
        "--log-level",
        choices=LOG_LEVEL_CHOICES,
        default="warning",
        help=(
            "Python logging level to use for troubleshooting output. "
            "Use 'debug' to trace filename normalization and API requests."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper()))

    console = Console()
    imdb_client = IMDBClient()
    renamer = MovieRenamer(
        imdb_client,
        console,
        rename_format=args.rename_format,
    )

    directory = Path(args.path)
    if not directory.exists() or not directory.is_dir():
        parser.error(f"Provided path is not a directory: {directory}")

    console.print(f"Scanning directory: {directory}")
    renamer.process_directory(directory, dry_run=args.dry_run, search_limit=args.limit)

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
