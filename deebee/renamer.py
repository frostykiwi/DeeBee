"""Filesystem utilities for DeeBee."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from rich.console import Console
from rich.table import Table

from .imdb_client import IMDBClient, IMDBMovie

INVALID_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9_.\- ]+")


@dataclass
class MovieCandidate:
    """Mapping between a file path and a proposed movie metadata match."""

    original_path: Path
    movie: IMDBMovie

    @property
    def proposed_filename(self) -> str:
        sanitized_title = INVALID_FILENAME_CHARS.sub("", self.movie.title)
        if self.movie.year:
            return f"{sanitized_title} ({self.movie.year}){self.original_path.suffix}"
        return f"{sanitized_title}{self.original_path.suffix}"

    @property
    def proposed_path(self) -> Path:
        return self.original_path.with_name(self.proposed_filename)


class MovieRenamer:
    """Core orchestrator for scanning directories and renaming movie files."""

    def __init__(self, imdb_client: IMDBClient, console: Optional[Console] = None) -> None:
        self._imdb_client = imdb_client
        self._console = console or Console()

    def process_directory(
        self,
        directory: Path,
        *,
        dry_run: bool = True,
        search_limit: int = 10,
    ) -> List[MovieCandidate]:
        """Process a directory containing movie files.

        Returns the chosen mappings for inspection by callers. When ``dry_run`` is
        ``False`` the filesystem is modified accordingly.
        """

        movie_files = self._discover_movie_files(directory)
        selected_candidates: List[MovieCandidate] = []

        for movie_file in movie_files:
            query = self._guess_search_query(movie_file)
            results = self._imdb_client.search(query, limit=search_limit)
            if not results:
                self._console.print(f"[yellow]No matches found for:[/] {movie_file.name}")
                continue

            chosen = self._prompt_for_choice(movie_file, results)
            if chosen is None:
                continue

            candidate = MovieCandidate(movie_file, chosen)
            selected_candidates.append(candidate)

            if dry_run:
                self._console.print(f"[cyan]DRY RUN:[/] {movie_file.name} -> {candidate.proposed_filename}")
            else:
                self._console.print(f"Renaming {movie_file.name} -> {candidate.proposed_filename}")
                movie_file.rename(candidate.proposed_path)

        return selected_candidates

    def _discover_movie_files(self, directory: Path) -> Iterable[Path]:
        return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".avi"})

    def _guess_search_query(self, path: Path) -> str:
        base = path.stem
        base = base.replace(".", " ")
        base = INVALID_FILENAME_CHARS.sub(" ", base)
        base = re.sub(r"\s+", " ", base)
        return base.strip()

    def _prompt_for_choice(self, file_path: Path, matches: List[IMDBMovie]) -> Optional[IMDBMovie]:
        table = Table(title=f"Matches for {file_path.name}")
        table.add_column("Index", justify="right")
        table.add_column("Title")
        table.add_column("Year")

        for index, movie in enumerate(matches, start=1):
            table.add_row(str(index), movie.title, movie.year or "?")

        table.add_row("0", "Skip", "")
        self._console.print(table)

        while True:
            choice = self._console.input("Select a match (0 to skip): ")
            if not choice.isdigit():
                self._console.print("[red]Invalid choice. Please enter a number.[/]")
                continue

            selection = int(choice)
            if selection == 0:
                return None
            if 1 <= selection <= len(matches):
                return matches[selection - 1]

            self._console.print("[red]Choice out of range.[/]")
