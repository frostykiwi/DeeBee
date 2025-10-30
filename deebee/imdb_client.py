"""Client for interacting with imdbapi.dev."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, TYPE_CHECKING

try:  # pragma: no cover - handled gracefully for optional dependency during tests
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover
    import requests as requests_type


logger = logging.getLogger(__name__)


@dataclass
class IMDBMovie:
    """Lightweight representation of an IMDB title search result."""

    id: str
    title: str
    year: Optional[str] = None
    episode_title: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: dict) -> "IMDBMovie":
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
            id=payload.get("id", ""),
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
        session: Optional["requests.Session"] = None,
        base_url: str = "https://api.imdbapi.dev",
        timeout: float = 5.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        """Create a new client.

        Parameters
        ----------
        api_key:
            Deprecated parameter retained for backward compatibility. The new
            search endpoint does not require authentication, so the value is
            ignored when provided.
        session:
            Optional custom :class:`requests.Session` instance, primarily used
            for testing.
        base_url:
            Base URL for the imdbapi.dev service.
        timeout:
            Number of seconds to wait for a response before aborting the request.
            Values less than or equal to zero disable the explicit timeout and
            fall back to the underlying ``requests`` default.
        max_retries:
            Total number of attempts to make for a search request before
            surfacing the error to callers.
        backoff_factor:
            Delay factor, in seconds, used for exponential backoff between
            retry attempts.
        """

        if requests is None:  # pragma: no cover - exercised in runtime environments without dependency
            raise RuntimeError("The 'requests' package is required to use IMDBClient.")

        self._session = session or requests.Session()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout if timeout and timeout > 0 else None
        self._max_retries = max(1, int(max_retries))
        self._backoff_factor = max(0.0, backoff_factor)
        # imdbapi.dev does not require authentication. The attribute is retained
        # to avoid breaking callers that still pass an ``api_key`` argument in
        # anticipation of the service introducing tokens in the future.
        self._api_key = api_key

    def search(self, query: str, *, limit: int = 10) -> List[IMDBMovie]:
        """Search for a movie title using the imdbapi.dev title endpoint."""

        if not query.strip():
            logger.debug("Ignoring blank search query for IMDB lookup")
            return []

        params = {"query": query, "limit": min(max(limit, 1), 50)}

        # Authentication headers are intentionally omitted because the public
        # imdbapi.dev endpoint is fully open. If the service ever requires
        # tokens, the commented logic below can be restored.
        # headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else None
        logger.debug("Requesting IMDB titles with query='%s' and limit=%d", query, params["limit"])

        attempt = 0
        last_error: Optional[Exception] = None
        while attempt < self._max_retries:
            try:
                response = self._session.get(
                    f"{self._base_url}/search/titles",
                    params=params,
                    timeout=self._timeout,
                    # headers=headers,
                )
                break
            except requests.exceptions.RequestException as exc:  # type: ignore[union-attr]
                last_error = exc
                attempt += 1
                if attempt >= self._max_retries:
                    logger.error(
                        "IMDB lookup failed after %d attempt(s) for query '%s'", attempt, query
                    )
                    raise
                delay = self._backoff_factor * (2 ** (attempt - 1))
                logger.warning(
                    "IMDB lookup error on attempt %d/%d for query '%s': %s. Retrying in %.2fs",
                    attempt,
                    self._max_retries,
                    query,
                    exc,
                    delay,
                )
                if delay:
                    time.sleep(delay)
        else:  # pragma: no cover - defensive guard, loop always breaks or raises
            if last_error is not None:
                raise last_error
            raise RuntimeError("IMDBClient search attempts exhausted without response.")
        response.raise_for_status()
        payload = response.json()

        results: Iterable[dict] = payload.get("titles") or payload.get("results", [])
        movies = [IMDBMovie.from_dict(item) for item in results]
        logger.debug("IMDB query '%s' returned %d result(s)", query, len(movies))
        return movies
