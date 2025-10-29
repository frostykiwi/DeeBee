"""Client for interacting with TheTVDB v4 API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, List, Optional, TYPE_CHECKING

try:  # pragma: no cover - optional dependency handling mirrors imdb client
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover
    import requests as requests_type


logger = logging.getLogger(__name__)


@dataclass
class TVDBSeries:
    """Lightweight representation of a TheTVDB search result."""

    id: int
    title: str
    year: Optional[str]

    @classmethod
    def from_dict(cls, payload: dict) -> "TVDBSeries":
        name = (
            payload.get("name")
            or payload.get("seriesName")
            or payload.get("translations", {}).get("name")
            or payload.get("slug")
            or ""
        )

        year_value: Optional[str] = None
        first_aired = payload.get("firstAired") or payload.get("year")
        if isinstance(first_aired, str) and first_aired:
            year_value = first_aired.split("-", 1)[0]
        elif isinstance(first_aired, int):
            year_value = str(first_aired)

        logger.debug(
            "Parsed TVDB series payload with id=%s name='%s' year=%s",
            payload.get("id"),
            name,
            year_value,
        )

        return cls(
            id=payload.get("id") or 0,
            title=name,
            year=year_value if year_value else None,
        )

    def display_text(self) -> str:
        if self.year:
            return f"{self.title} ({self.year})"
        return self.title


class TheTVDBClient:
    """HTTP client wrapper for TheTVDB v4 search endpoints."""

    def __init__(
        self,
        *,
        api_key: str,
        session: Optional["requests_type.Session"] = None,
        base_url: str = "https://api4.thetvdb.com/v4",
    ) -> None:
        if requests is None:  # pragma: no cover - runtime dependency guard
            raise RuntimeError("The 'requests' package is required to use TheTVDBClient.")

        if not api_key:
            raise ValueError("A TheTVDB API key must be provided.")

        self._session = session or requests.Session()
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    def _authenticate(self) -> str:
        needs_refresh = True
        if self._token and self._token_expiry:
            needs_refresh = datetime.utcnow() >= self._token_expiry

        if needs_refresh:
            response = self._session.post(
                f"{self._base_url}/login",
                json={"apikey": self._api_key},
            )
            response.raise_for_status()
            payload = response.json().get("data", {})
            token = payload.get("token")
            if not token:
                raise RuntimeError("TheTVDB API response did not include an authentication token.")

            # Tokens are valid for one hour per API documentation. Refresh slightly earlier.
            self._token = token
            self._token_expiry = datetime.utcnow() + timedelta(minutes=50)

        if not self._token:
            raise RuntimeError("Failed to authenticate with TheTVDB.")

        return self._token

    def _authorized_headers(self) -> dict[str, str]:
        token = self._authenticate()
        return {"Authorization": f"Bearer {token}"}

    def search(self, query: str, *, limit: int = 10) -> List[TVDBSeries]:
        """Search for series on TheTVDB matching ``query``."""

        if not query.strip():
            logger.debug("Ignoring blank search query for TheTVDB lookup")
            return []

        headers = self._authorized_headers()
        params = {"q": query, "type": "series"}
        logger.debug(
            "Requesting TVDB search for query='%s' with limit=%d",
            query,
            min(max(limit, 1), 50),
        )
        response = self._session.get(f"{self._base_url}/search", params=params, headers=headers)
        if response.status_code == 401:
            # Token expired – refresh once.
            self._token = None
            headers = self._authorized_headers()
            response = self._session.get(f"{self._base_url}/search", params=params, headers=headers)

        response.raise_for_status()
        payload = response.json()
        results: Iterable[dict] = payload.get("data", [])
        series_list = [TVDBSeries.from_dict(item) for item in results]
        logger.debug("TVDB query '%s' returned %d result(s)", query, len(series_list))
        normalized_limit = min(max(limit, 1), 50)
        return series_list[:normalized_limit]
