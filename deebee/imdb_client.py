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
        return cls(
            id=payload.get("id", ""),
            title=payload.get("title", ""),
            year=payload.get("year"),
        )

    def display_text(self) -> str:
        if self.year:
            return f"{self.title} ({self.year})"
        return self.title


class IMDBClient:
    """HTTP client wrapper for imdbapi.dev searches."""

    def __init__(self, api_key: str, *, session: Optional["requests.Session"] = None) -> None:
        if requests is None:  # pragma: no cover - exercised in runtime environments without dependency
            raise RuntimeError("The 'requests' package is required to use IMDBClient.")

        self._api_key = api_key
        self._session = session or requests.Session()
        self._base_url = "https://imdbapi.dev/api"

    def search(self, query: str, *, limit: int = 10) -> List[IMDBMovie]:
        """Search for a movie title using the imdbapi.dev title endpoint."""

        if not query.strip():
            return []

        params = {"search": query, "limit": limit}
        response = self._session.get(
            f"{self._base_url}/search", params=params, headers={"Authorization": f"Bearer {self._api_key}"}
        )
        response.raise_for_status()
        payload = response.json()

        results: Iterable[dict] = payload.get("results", [])
        return [IMDBMovie.from_dict(item) for item in results]
