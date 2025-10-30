"""TV-specific renaming logic."""
from __future__ import annotations

import logging
from typing import List, Optional, TypeVar

from rich.console import Console

from .rename_common import (
    BaseRenamer,
    MediaMetadata,
    MediaSearchClient,
    MediaSearchQuery,
    RenameContext,
    RenameFormatSpec,
)


logger = logging.getLogger(__name__)


TMetadata = TypeVar("TMetadata", bound=MediaMetadata)


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


TV_RENAME_FORMATS: dict[str, RenameFormatSpec] = {
    "show_episode_numbers": RenameFormatSpec(
        "show_episode_numbers",
        "TV Show Name - Episode Name - S##E##",
        _format_show_episode_with_numbers,
    ),
    "show_numbers": RenameFormatSpec(
        "show_numbers",
        "TV Show Name - S##E##",
        _format_show_with_numbers,
    ),
    "show_episode": RenameFormatSpec(
        "show_episode",
        "TV Show Name - Episode Name",
        _format_show_episode,
    ),
    "show_only": RenameFormatSpec(
        "show_only",
        "TV Show Name",
        _format_show_only,
    ),
}

DEFAULT_TV_RENAME_FORMAT_KEY = "show_episode_numbers"


class TVRenamer(BaseRenamer[TMetadata]):
    """Renamer dedicated to TV episode files."""

    RENAME_FORMATS = TV_RENAME_FORMATS
    DEFAULT_RENAME_FORMAT_KEY = DEFAULT_TV_RENAME_FORMAT_KEY

    def __init__(
        self,
        media_client: MediaSearchClient[TMetadata],
        console: Optional[Console] = None,
        *,
        rename_format: Optional[str] = None,
    ) -> None:
        super().__init__(media_client, console=console, rename_format=rename_format)

    def _perform_search(
        self, search_info: MediaSearchQuery, limit: int
    ) -> List[TMetadata]:  # type: ignore[override]
        """Search for TV metadata, preferring episode lookups when available."""

        client = self._media_client
        season = search_info.season_number
        episode = search_info.episode_number

        if season is not None and episode is not None:
            search_episode = getattr(client, "search_episode", None)
            if callable(search_episode):
                try:
                    results = search_episode(
                        search_info.query,
                        season,
                        episode,
                        limit=limit,
                    )
                except Exception as exc:  # pragma: no cover - runtime logging aid
                    logger.debug(
                        "Episode-specific lookup failed for query='%s' season=%s episode=%s: %s",
                        search_info.query,
                        season,
                        episode,
                        exc,
                    )
                else:
                    if results:
                        return results

        return super()._perform_search(search_info, limit)
