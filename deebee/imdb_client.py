"""Client for interacting with imdbapi.dev."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, TYPE_CHECKING

try:  # pragma: no cover - handled gracefully for optional dependency during tests
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover
    import requests as requests_type


logger = logging.getLogger(__name__)


@dataclass
class IMDBMovie:
    """Lightweight representation of an IMDB title or episode."""

    id: str
    title: str
    year: Optional[str] = None
    episode_title: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "IMDBMovie":
        title = (
            payload.get("primaryTitle")
            or payload.get("originalTitle")
            or (payload.get("titleText") or {}).get("text")
            or payload.get("title", "")
        )

        year_value = (
            payload.get("startYear")
            or (payload.get("releaseYear") or {}).get("year")
            or (payload.get("titleYear") or {}).get("year")
            or payload.get("year")
        )
        year = str(year_value) if year_value else None

        episode_title = (
            (payload.get("episodeTitle") or {}).get("text")
            if isinstance(payload.get("episodeTitle"), dict)
            else payload.get("episodeTitle")
        )
        if not episode_title:
            episode = payload.get("episodeTitle") or payload.get("episode")
            if isinstance(episode, dict):
                episode_title = episode.get("title") or episode.get("name")
            elif isinstance(episode, str):
                episode_title = episode

        return cls(
            id=str(payload.get("id", "")),
            title=title,
            year=year,
            episode_title=episode_title if episode_title else None,
        )

    def display_text(self) -> str:
        if self.year:
            return f"{self.title} ({self.year})"
        return self.title


class IMDBClient:
    """HTTP client wrapper for imdbapi.dev searches."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        session: Optional["requests_type.Session"] = None,
        base_url: str = "https://api.imdbapi.dev",
        timeout: float = 5.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        """Create a new client."""

        if requests is None:  # pragma: no cover - exercised in runtime environments without dependency
            raise RuntimeError("The 'requests' package is required to use IMDBClient.")

        self._session: "requests_type.Session" = session or requests.Session()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout if timeout and timeout > 0 else None
        self._max_retries = max(1, int(max_retries))
        self._backoff_factor = max(0.0, backoff_factor)
        # imdbapi.dev does not require authentication. The attribute is retained
        # to avoid breaking callers that still pass an ``api_key`` argument in
        # anticipation of the service introducing tokens in the future.
        self._api_key = api_key

    # ------------------------------------------------------------------
    # Core HTTP helpers
    # ------------------------------------------------------------------
    def _request(self, path: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute an HTTP GET request against the imdbapi.dev service."""

        attempt = 0
        last_error: Optional[Exception] = None
        url = f"{self._base_url}{path}"
        logger.debug("Requesting IMDB endpoint %s with params=%s", url, params)

        while attempt < self._max_retries:
            try:
                response = self._session.get(url, params=params, timeout=self._timeout)
                response.raise_for_status()
                payload = response.json()
            except requests.exceptions.RequestException as exc:  # type: ignore[union-attr]
                last_error = exc
                attempt += 1
                if attempt >= self._max_retries:
                    logger.error(
                        "IMDB request to %s failed after %d attempt(s)",
                        url,
                        attempt,
                    )
                    raise
                delay = self._backoff_factor * (2 ** (attempt - 1))
                logger.warning(
                    "IMDB request error on attempt %d/%d for %s: %s. Retrying in %.2fs",
                    attempt,
                    self._max_retries,
                    url,
                    exc,
                    delay,
                )
                if delay:
                    time.sleep(delay)
                continue

            if isinstance(payload, dict):
                return payload

            logger.debug("Non-dict payload received from %s; coercing to empty dict", url)
            return {}

        if last_error is not None:  # pragma: no cover - defensive guard
            raise last_error
        raise RuntimeError("IMDBClient request attempts exhausted without response.")

    def _search_titles_raw(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Return the raw payload entries for a title search."""

        params = {"query": query, "limit": min(max(limit, 1), 50)}
        payload = self._request("/search/titles", params=params)
        raw_results: Iterable[Any] = payload.get("titles") or payload.get("results") or []
        results: List[Dict[str, Any]] = [item for item in raw_results if isinstance(item, dict)]
        logger.debug("IMDB title search '%s' produced %d raw result(s)", query, len(results))
        return results

    @staticmethod
    def _extract_text(value: Any) -> Optional[str]:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        if isinstance(value, dict):
            for key in ("text", "title", "name"):
                text_value = value.get(key)
                if isinstance(text_value, str) and text_value.strip():
                    return text_value.strip()
        return None

    def _extract_episode_from_collection(
        self, episodes: Iterable[Any], episode_number: int
    ) -> Optional[Dict[str, Any]]:
        """Return the episode payload matching ``episode_number`` if available."""

        fallback: Optional[Dict[str, Any]] = None
        for entry in episodes:
            if not isinstance(entry, dict):
                continue
            if fallback is None:
                fallback = entry
            number = entry.get("episodeNumber")
            try:
                number_value = int(number)
            except (TypeError, ValueError):
                continue
            if number_value == episode_number:
                return entry
        return fallback

    def _resolve_episode_title(self, payload: Dict[str, Any]) -> Optional[str]:
        """Extract a displayable episode title from the payload."""

        for key in ("title", "primaryTitle", "episodeTitle", "name", "originalTitle"):
            title = self._extract_text(payload.get(key))
            if title:
                return title
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def search(self, query: str, *, limit: int = 10) -> List[IMDBMovie]:
        """Search for a movie or TV title using the imdbapi.dev title endpoint."""

        normalized = query.strip()
        if not normalized:
            logger.debug("Ignoring blank search query for IMDB lookup")
            return []

        items = self._search_titles_raw(normalized, limit)
        movies = [IMDBMovie.from_dict(item) for item in items]
        logger.debug("IMDB query '%s' returned %d result(s)", normalized, len(movies))
        return movies

    def search_episode(
        self,
        query: str,
        season_number: int,
        episode_number: int,
        *,
        limit: int = 10,
    ) -> List[IMDBMovie]:
        """Return TV episode metadata using the imdbapi.dev episode listings."""

        normalized = query.strip()
        if not normalized:
            logger.debug("Ignoring blank search query for IMDB episode lookup")
            return []

        results: List[IMDBMovie] = []
        series_candidates = self._search_titles_raw(normalized, limit)

        for candidate in series_candidates:
            if len(results) >= limit:
                break

            series_id = candidate.get("id")
            if not series_id:
                continue

            series_metadata = IMDBMovie.from_dict(candidate)
            try:
                payload = self._request(
                    f"/titles/{series_id}/episodes",
                    params={
                        "season": str(season_number),
                        "pageSize": min(max(limit, 1) * 5, 50),
                    },
                )
            except requests.exceptions.RequestException:  # type: ignore[union-attr]
                logger.debug(
                    "Episode lookup failed for series id=%s season=%s episode=%s",
                    series_id,
                    season_number,
                    episode_number,
                    exc_info=True,
                )
                continue

            episodes = payload.get("episodes")
            if not isinstance(episodes, Iterable):
                logger.debug("No episodes found for series id=%s in season %s", series_id, season_number)
                continue

            episode_payload = self._extract_episode_from_collection(episodes, episode_number)
            if not episode_payload:
                logger.debug(
                    "Episode number %s not found for series id=%s season=%s",
                    episode_number,
                    series_id,
                    season_number,
                )
                continue

            episode_title = self._resolve_episode_title(episode_payload)
            if not episode_title:
                logger.debug("Unable to resolve episode title for series id=%s", series_id)
                continue

            episode_id = episode_payload.get("id") or series_metadata.id
            results.append(
                IMDBMovie(
                    id=str(episode_id),
                    title=series_metadata.title,
                    year=series_metadata.year,
                    episode_title=episode_title,
                )
            )

        logger.debug(
            "IMDB episode query '%s' S%02dE%02d returned %d result(s)",
            normalized,
            season_number,
            episode_number,
            len(results),
        )
        return results
