"""Filesystem utilities for DeeBee."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Protocol, TypeVar, Generic

from rich.console import Console
from rich.table import Table


logger = logging.getLogger(__name__)



class MediaMetadata(Protocol):
    """Protocol describing the fields required for rename operations."""

    title: str
    year: Optional[str]


TMetadata = TypeVar("TMetadata", bound=MediaMetadata)


class MediaSearchClient(Protocol[TMetadata]):
    """Protocol describing a metadata search client."""

    def search(self, query: str, *, limit: int = 10) -> List[TMetadata]:  # pragma: no cover - protocol definition
        """Return search results for the provided query."""

INVALID_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9_.\- ]+")

NameBuilder = Callable[[str, Optional[str]], str]


@dataclass(frozen=True)
class RenameFormatSpec:
    """Description of an available rename format."""

    key: str
    label: str
    builder: NameBuilder

    def build_name(self, title: str, year: Optional[str]) -> str:
        """Return the filename (without extension) for the provided metadata."""

        name = self.builder(title, year)
        name = re.sub(r"\s+", " ", name).strip()
        return name or title


def _format_title_year(title: str, year: Optional[str]) -> str:
    return f"{title} ({year})" if year else title


def _format_title_dash_year(title: str, year: Optional[str]) -> str:
    return f"{title} - {year}" if year else title


def _format_year_dash_title(title: str, year: Optional[str]) -> str:
    return f"{year} - {title}" if year else title


def _format_title_only(title: str, year: Optional[str]) -> str:  # noqa: ARG001
    return title


def _format_title_brackets_year(title: str, year: Optional[str]) -> str:
    return f"{title} [{year}]" if year else title


AVAILABLE_RENAME_FORMATS = {
    "title_year": RenameFormatSpec("title_year", "Title (Year)", _format_title_year),
    "title_dash_year": RenameFormatSpec("title_dash_year", "Title - Year", _format_title_dash_year),
    "year_dash_title": RenameFormatSpec("year_dash_title", "Year - Title", _format_year_dash_title),
    "title_only": RenameFormatSpec("title_only", "Title", _format_title_only),
    "title_brackets_year": RenameFormatSpec(
        "title_brackets_year",
        "Title [Year]",
        _format_title_brackets_year,
    ),
}

DEFAULT_RENAME_FORMAT_KEY = "title_year"


def _sanitize_title(title: str) -> str:
    sanitized = INVALID_FILENAME_CHARS.sub("", title)
    sanitized = re.sub(r"\s+", " ", sanitized)
    return sanitized.strip()


@dataclass
class MovieCandidate(Generic[TMetadata]):
    """Mapping between a file path and a proposed movie metadata match."""

    original_path: Path
    movie: TMetadata
    format_spec: RenameFormatSpec

    @property
    def proposed_filename(self) -> str:
        sanitized_title = _sanitize_title(self.movie.title)
        filename = self.format_spec.build_name(sanitized_title, self.movie.year)
        return f"{filename}{self.original_path.suffix}"

    @property
    def proposed_path(self) -> Path:
        return self.original_path.with_name(self.proposed_filename)


class MovieRenamer(Generic[TMetadata]):
    """Core orchestrator for scanning directories and renaming movie files."""

    def __init__(
        self,
        imdb_client: MediaSearchClient[TMetadata],
        console: Optional[Console] = None,
        *,
        rename_format: str = DEFAULT_RENAME_FORMAT_KEY,
    ) -> None:
        self._imdb_client = imdb_client
        self._console = console or Console()
        self._format_spec = self._resolve_format(rename_format)

    @staticmethod
    def available_formats() -> List[RenameFormatSpec]:
        """Return the available rename format specifications."""

        return list(AVAILABLE_RENAME_FORMATS.values())

    @staticmethod
    def _resolve_format(key: str) -> RenameFormatSpec:
        try:
            return AVAILABLE_RENAME_FORMATS[key]
        except KeyError as exc:  # pragma: no cover - defensive programming
            available = ", ".join(sorted(AVAILABLE_RENAME_FORMATS))
            raise ValueError(f"Unknown rename format '{key}'. Available: {available}") from exc

    def process_directory(
        self,
        directory: Path,
        *,
        dry_run: bool = True,
        search_limit: int = 10,
    ) -> List[MovieCandidate[TMetadata]]:
        """Process a directory containing movie files.

        Returns the chosen mappings for inspection by callers. When ``dry_run`` is
        ``False`` the filesystem is modified accordingly.
        """

        movie_files = list(self._discover_movie_files(directory))
        logger.debug("Discovered %d candidate file(s) in %s", len(movie_files), directory)
        selected_candidates: List[MovieCandidate[TMetadata]] = []

        for movie_file in movie_files:
            logger.debug("Processing file: %s", movie_file)
            query = self._guess_search_query(movie_file)
            logger.debug("Search query for %s resolved to '%s'", movie_file.name, query)
            results = self._imdb_client.search(query, limit=search_limit)
            logger.debug(
                "Received %d result(s) for query '%s' (limit=%d)",
                len(results),
                query,
                search_limit,
            )
            if not results:
                self._console.print(f"[yellow]No matches found for:[/] {movie_file.name}")
                continue

            chosen = self._prompt_for_choice(movie_file, results)
            if chosen is None:
                continue

            candidate = MovieCandidate(movie_file, chosen, self._format_spec)
            selected_candidates.append(candidate)

            if dry_run:
                self._console.print(f"[cyan]DRY RUN:[/] {movie_file.name} -> {candidate.proposed_filename}")
            else:
                self._console.print(f"Renaming {movie_file.name} -> {candidate.proposed_filename}")
                movie_file.rename(candidate.proposed_path)

        return selected_candidates

    def _discover_movie_files(self, directory: Path) -> Iterable[Path]:
        files = sorted(
            p
            for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".avi"}
        )
        logger.debug("Filtered %d supported media file(s) in %s", len(files), directory)
        return files

    def _guess_search_query(self, path: Path) -> str:
        base = path.stem
        logger.debug("Original filename stem for %s: '%s'", path.name, base)
        base = base.replace(".", " ")
        base = INVALID_FILENAME_CHARS.sub(" ", base)
        base = re.sub(r"\s+", " ", base)
        query = base.strip()
        logger.debug("Normalized search query for %s: '%s'", path.name, query)
        return query

    def _prompt_for_choice(
        self, file_path: Path, matches: List[TMetadata]
    ) -> Optional[TMetadata]:
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
