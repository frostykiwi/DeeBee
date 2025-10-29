"""Client for interacting with imdbapi.dev."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, TYPE_CHECKING

try:  # pragma: no cover - handled gracefully for optional dependency during tests
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover
    import requests as requests_type


@dataclass
class IMDBMovie:
    """Lightweight representation of an IMDB title search result."""

    id: str
    title: str
    year: Optional[str]

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

        return cls(
            id=payload.get("id", ""),
            title=title,
            year=year,
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
        """

        if requests is None:  # pragma: no cover - exercised in runtime environments without dependency
            raise RuntimeError("The 'requests' package is required to use IMDBClient.")

        self._session = session or requests.Session()
        self._base_url = base_url.rstrip("/")
        # imdbapi.dev does not require authentication. The attribute is retained
        # to avoid breaking callers that still pass an ``api_key`` argument in
        # anticipation of the service introducing tokens in the future.
        self._api_key = api_key

    def search(self, query: str, *, limit: int = 10) -> List[IMDBMovie]:
        """Search for a movie title using the imdbapi.dev title endpoint."""

        if not query.strip():
            return []

        params = {"query": query, "limit": min(max(limit, 1), 50)}

        # Authentication headers are intentionally omitted because the public
        # imdbapi.dev endpoint is fully open. If the service ever requires
        # tokens, the commented logic below can be restored.
        # headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else None
        response = self._session.get(
            f"{self._base_url}/search/titles",
            params=params,
            # headers=headers,
        )
        response.raise_for_status()
        payload = response.json()

        results: Iterable[dict] = payload.get("titles") or payload.get("results", [])
        return [IMDBMovie.from_dict(item) for item in results]
