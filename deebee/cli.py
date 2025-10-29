"""Command line interface for DeeBee."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from rich.console import Console

from .imdb_client import IMDBClient
from .renamer import MovieRenamer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DeeBee movie library organizer")
    parser.add_argument(
        "path",
        nargs="?",
        default=os.getcwd(),
        help="Directory containing movie files to process",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        default=os.environ.get("IMDB_API_KEY"),
        help="API key for imdbapi.dev (defaults to IMDB_API_KEY env var)",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.api_key:
        parser.error("An API key is required. Set --api-key or IMDB_API_KEY environment variable.")

    console = Console()
    imdb_client = IMDBClient(args.api_key)
    renamer = MovieRenamer(imdb_client, console)

    directory = Path(args.path)
    if not directory.exists() or not directory.is_dir():
        parser.error(f"Provided path is not a directory: {directory}")

    console.print(f"Scanning directory: {directory}")
    renamer.process_directory(directory, dry_run=args.dry_run, search_limit=args.limit)

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
