"""Movie-specific renaming logic."""
from __future__ import annotations

from typing import Optional, TypeVar

from rich.console import Console

from .rename_common import (
    BaseRenamer,
    MediaMetadata,
    MediaSearchClient,
    RenameContext,
    RenameFormatSpec,
)


TMetadata = TypeVar("TMetadata", bound=MediaMetadata)


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
    ),
    "movie_title_year": RenameFormatSpec(
        "movie_title_year",
        "Movie Title (Year)",
        _format_movie_title_with_year,
    ),
}

DEFAULT_MOVIE_RENAME_FORMAT_KEY = "movie_title"


class MovieRenamer(BaseRenamer[TMetadata]):
    """Renamer dedicated to movie files."""

    RENAME_FORMATS = MOVIE_RENAME_FORMATS
    DEFAULT_RENAME_FORMAT_KEY = DEFAULT_MOVIE_RENAME_FORMAT_KEY

    def __init__(
        self,
        media_client: MediaSearchClient[TMetadata],
        console: Optional[Console] = None,
        *,
        rename_format: Optional[str] = None,
    ) -> None:
        super().__init__(media_client, console=console, rename_format=rename_format)
