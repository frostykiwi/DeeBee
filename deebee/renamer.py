"""Filesystem utilities for DeeBee."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Protocol, Tuple, TypeVar, Generic

from rich.console import Console
from rich.table import Table


logger = logging.getLogger(__name__)



class MediaMetadata(Protocol):
    """Protocol describing the fields required for rename operations."""

    title: str
    year: Optional[str]
    episode_title: Optional[str]


TMetadata = TypeVar("TMetadata", bound=MediaMetadata)


class MediaSearchClient(Protocol[TMetadata]):
    """Protocol describing a metadata search client."""

    def search(self, query: str, *, limit: int = 10) -> List[TMetadata]:  # pragma: no cover - protocol definition
        """Return search results for the provided query."""

INVALID_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9_.\- ]+")
YEAR_TOKEN_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
SEASON_EPISODE_PATTERNS = (
    re.compile(r"(?i)\bS(?P<season>\d{1,3})[ ._-]*E(?P<episode>\d{1,3})\b"),
    re.compile(r"(?i)\b(?P<season>\d{1,3})x(?P<episode>\d{1,3})\b"),
    re.compile(
        r"(?i)\bseason[ ._-]*(?P<season>\d{1,3})[ ._-]*(?:episode|ep)[ ._-]*(?P<episode>\d{1,3})\b"
    ),
)
RELEASE_METADATA_TOKENS = {
    "480p",
    "720p",
    "1080p",
    "2160p",
    "webdl",
    "webrip",
    "web",
    "hdtv",
    "hdrip",
    "bluray",
    "brrip",
    "dvdrip",
    "hdr",
    "x264",
    "x265",
    "h264",
    "h265",
    "hevc",
    "proper",
    "repack",
    "extended",
    "unrated",
    "remux",
    "aac",
    "ac3",
    "dts",
    "ddp",
    "atmos",
}


def _strip_trailing_release_tokens(value: str) -> str:
    tokens = value.strip().split()
    while tokens:
        token = tokens[-1]
        normalized = token.casefold().replace("-", "")
        if re.fullmatch(r"\d{3,4}p", normalized):
            tokens.pop()
            continue
        if normalized.startswith("ddp") and normalized[3:].replace(".", "").isdigit():
            tokens.pop()
            continue
        if normalized in RELEASE_METADATA_TOKENS:
            tokens.pop()
            continue
        break
    return " ".join(tokens)


@dataclass(frozen=True)
class RenameContext:
    """Information required to generate a filename for media items."""

    series_title: str
    episode_title: Optional[str]
    year: Optional[str]
    season_number: Optional[int]
    episode_number: Optional[int]


NameBuilder = Callable[[RenameContext], str]


@dataclass(frozen=True)
class MediaSearchQuery:
    """Information extracted from a filename for API searches."""

    query: str
    season_number: Optional[int]
    episode_number: Optional[int]


@dataclass(frozen=True)
class RenameFormatSpec:
    """Description of an available rename format."""

    key: str
    label: str
    builder: NameBuilder
    modes: tuple[str, ...] = ("movie", "tv")

    def build_name(self, context: RenameContext) -> str:
        """Return the filename (without extension) for the provided metadata."""

        name = self.builder(context)
        name = re.sub(r"\s+", " ", name).strip()
        return name or context.series_title

    def supports_mode(self, mode: str) -> bool:
        """Return ``True`` if this format can be used for ``mode``."""

        normalized = mode.lower()
        return normalized in self.modes


def _format_show_episode_with_numbers(context: RenameContext) -> str:
    parts: list[str] = [context.series_title]
    if context.episode_title:
        parts.append(context.episode_title)
    season = context.season_number
    episode = context.episode_number
    if season is not None and episode is not None:
        parts.append(f"S{season:02d}E{episode:02d}")
    return " - ".join(part for part in parts if part)


def _format_show_with_numbers(context: RenameContext) -> str:
    season = context.season_number
    episode = context.episode_number
    suffix = f" - S{season:02d}E{episode:02d}" if season is not None and episode is not None else ""
    return f"{context.series_title}{suffix}"


def _format_show_episode(context: RenameContext) -> str:
    if context.episode_title:
        return f"{context.series_title} - {context.episode_title}"
    return context.series_title


def _format_show_only(context: RenameContext) -> str:
    return context.series_title


def _format_movie_title_with_year(context: RenameContext) -> str:
    if context.year:
        return f"{context.series_title} ({context.year})"
    return context.series_title


def _format_movie_title(context: RenameContext) -> str:
    return context.series_title


MOVIE_RENAME_FORMATS: dict[str, RenameFormatSpec] = {
    "movie_title": RenameFormatSpec(
        "movie_title",
        "Movie Title",
        _format_movie_title,
        ("movie",),
    ),
    "movie_title_year": RenameFormatSpec(
        "movie_title_year",
        "Movie Title (Year)",
        _format_movie_title_with_year,
        ("movie",),
    ),
}

TV_RENAME_FORMATS: dict[str, RenameFormatSpec] = {
    "show_episode_numbers": RenameFormatSpec(
        "show_episode_numbers",
        "TV Show Name - Episode Name - S##E##",
        _format_show_episode_with_numbers,
        ("tv",),
    ),
    "show_numbers": RenameFormatSpec(
        "show_numbers",
        "TV Show Name - S##E##",
        _format_show_with_numbers,
        ("tv",),
    ),
    "show_episode": RenameFormatSpec(
        "show_episode",
        "TV Show Name - Episode Name",
        _format_show_episode,
        ("tv",),
    ),
    "show_only": RenameFormatSpec(
        "show_only",
        "TV Show Name",
        _format_show_only,
        ("tv",),
    ),
}

AVAILABLE_RENAME_FORMATS: dict[str, RenameFormatSpec] = {
    **MOVIE_RENAME_FORMATS,
    **TV_RENAME_FORMATS,
}

DEFAULT_RENAME_FORMAT_KEY = "movie_title"
DEFAULT_TV_RENAME_FORMAT_KEY = "show_episode_numbers"


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
    season_number: Optional[int] = None
    episode_number: Optional[int] = None

    @property
    def proposed_filename(self) -> str:
        sanitized_title = _sanitize_title(self.movie.title)
        raw_episode = getattr(self.movie, "episode_title", None)
        sanitized_episode = _sanitize_title(raw_episode) if raw_episode else None
        context = RenameContext(
            series_title=sanitized_title,
            episode_title=sanitized_episode,
            year=self.movie.year,
            season_number=self.season_number,
            episode_number=self.episode_number,
        )
        filename = self.format_spec.build_name(context)
        if self.season_number is not None and self.episode_number is not None:
            # Ensure season/episode markers are present for formats that omit them.
            if f"S{self.season_number:02d}E{self.episode_number:02d}" not in filename:
                filename = f"{filename} S{self.season_number:02d}E{self.episode_number:02d}"
        return f"{filename}{self.original_path.suffix}"

    @property
    def proposed_path(self) -> Path:
        return self.original_path.with_name(self.proposed_filename)


class MovieRenamer(Generic[TMetadata]):
    """Core orchestrator for scanning directories and renaming media files."""

    def __init__(
        self,
        media_client: MediaSearchClient[TMetadata],
        console: Optional[Console] = None,
        *,
        rename_format: Optional[str] = None,
        media_mode: str = "movie",
    ) -> None:
        self._media_client = media_client
        self._console = console or Console()
        self._media_mode = media_mode.lower()
        if self._media_mode not in {"movie", "tv"}:
            raise ValueError("media_mode must be either 'movie' or 'tv'.")

        if rename_format is None:
            rename_format = (
                DEFAULT_TV_RENAME_FORMAT_KEY
                if self._media_mode == "tv"
                else DEFAULT_RENAME_FORMAT_KEY
            )

        self._format_spec = self._resolve_format(rename_format, self._media_mode)

    @staticmethod
    def available_formats(mode: Optional[str] = None) -> List[RenameFormatSpec]:
        """Return the available rename format specifications."""

        if mode is None:
            return list(AVAILABLE_RENAME_FORMATS.values())

        normalized = mode.lower()
        if normalized not in {"movie", "tv"}:
            raise ValueError("mode must be 'movie', 'tv', or None")

        return [
            spec
            for spec in AVAILABLE_RENAME_FORMATS.values()
            if spec.supports_mode(normalized)
        ]

    @staticmethod
    def _resolve_format(key: str, mode: Optional[str] = None) -> RenameFormatSpec:
        try:
            spec = AVAILABLE_RENAME_FORMATS[key]
        except KeyError as exc:  # pragma: no cover - defensive programming
            available = ", ".join(sorted(AVAILABLE_RENAME_FORMATS))
            raise ValueError(f"Unknown rename format '{key}'. Available: {available}") from exc

        if mode is not None and not spec.supports_mode(mode):
            raise ValueError(f"Rename format '{key}' is not valid for {mode} mode.")

        return spec

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
            search_info = self._prepare_search(movie_file)
            query = search_info.query
            logger.debug(
                "Search query for %s resolved to '%s' (season=%s, episode=%s)",
                movie_file.name,
                query,
                search_info.season_number,
                search_info.episode_number,
            )
            results = self._media_client.search(query, limit=search_limit)
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

            candidate = MovieCandidate(
                movie_file,
                chosen,
                self._format_spec,
                season_number=search_info.season_number,
                episode_number=search_info.episode_number,
            )
            selected_candidates.append(candidate)

            target_path, adjusted = self._determine_target_path(candidate)
            display_name = target_path.name

            if dry_run:
                self._console.print(f"[cyan]DRY RUN:[/] {movie_file.name} -> {display_name}")
                if adjusted:
                    self._console.print(
                        f"[yellow]Note:[/] {candidate.proposed_filename} already exists. Would use {display_name} instead."
                    )
            else:
                if adjusted:
                    self._console.print(
                        f"[yellow]Adjusted target to avoid overwrite:[/] {candidate.proposed_filename} -> {display_name}"
                    )
                self._console.print(f"Renaming {movie_file.name} -> {display_name}")
                movie_file.rename(target_path)

        return selected_candidates

    def _discover_movie_files(self, directory: Path) -> Iterable[Path]:
        files = sorted(
            p
            for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".avi"}
        )
        logger.debug("Filtered %d supported media file(s) in %s", len(files), directory)
        return files

    def _prepare_search(self, path: Path) -> MediaSearchQuery:
        """Extract the API query and optional episode numbers from ``path``."""

        base = path.stem
        logger.debug("Original filename stem for %s: '%s'", path.name, base)

        season_number: Optional[int] = None
        episode_number: Optional[int] = None

        for pattern in SEASON_EPISODE_PATTERNS:
            match = pattern.search(base)
            if match:
                try:
                    season_number = int(match.group("season"))
                    episode_number = int(match.group("episode"))
                except (TypeError, ValueError):
                    season_number = None
                    episode_number = None
                else:
                    logger.debug(
                        "Detected season/episode markers for %s: season=%s episode=%s",
                        path.name,
                        season_number,
                        episode_number,
                    )
                start, end = match.span()
                base = base[:start] + base[end:]
                base = re.sub(r"[\s._-]+$", "", base)
                break

        base = base.replace(".", " ")
        base = INVALID_FILENAME_CHARS.sub(" ", base)
        base = re.sub(r"\s+", " ", base)
        base = _strip_trailing_release_tokens(base)

        if season_number is not None or episode_number is not None:
            base = YEAR_TOKEN_PATTERN.sub(" ", base)
            base = re.sub(r"\s+", " ", base)

        query = base.strip()
        logger.debug("Normalized search query for %s: '%s'", path.name, query)

        return MediaSearchQuery(query=query, season_number=season_number, episode_number=episode_number)

    def _determine_target_path(self, candidate: MovieCandidate[TMetadata]) -> Tuple[Path, bool]:
        """Return a filesystem path for ``candidate`` that avoids clobbering existing files."""

        proposed_path = candidate.proposed_path
        if not proposed_path.exists():
            return proposed_path, False

        stem = proposed_path.stem
        suffix = proposed_path.suffix
        counter = 1
        while True:
            alternative = proposed_path.with_name(f"{stem} ({counter}){suffix}")
            if not alternative.exists():
                return alternative, True
            counter += 1

    def _guess_search_query(self, path: Path) -> str:
        return self._prepare_search(path).query

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
