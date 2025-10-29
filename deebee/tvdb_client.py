"""Client for interacting with TheTVDB v4 API."""
from __future__ import annotations

import importlib
import inspect
import logging
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional


logger = logging.getLogger(__name__)


def _coerce_payload(payload: Any) -> dict[str, Any]:
    """Convert SDK models into a dictionary of primitive values."""

    if isinstance(payload, dict):
        return payload
    if hasattr(payload, "model_dump"):
        try:
            dumped = payload.model_dump()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive conversion
            dumped = None
        else:
            if isinstance(dumped, dict):
                return dumped
    if hasattr(payload, "to_dict"):
        try:
            dumped = payload.to_dict()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive conversion
            dumped = None
        else:
            if isinstance(dumped, dict):
                return dumped
    if hasattr(payload, "dict"):
        try:
            dumped = payload.dict()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover
            dumped = None
        else:
            if isinstance(dumped, dict):
                return dumped
    if hasattr(payload, "_asdict"):
        try:
            dumped = payload._asdict()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover
            dumped = None
        else:
            if isinstance(dumped, dict):
                return dumped
    if hasattr(payload, "__dict__"):
        data = {key: value for key, value in vars(payload).items() if not key.startswith("_")}
        if data:
            return data
    return {"id": getattr(payload, "id", 0), "name": getattr(payload, "name", "")}


@dataclass
class TVDBSeries:
    """Lightweight representation of a TheTVDB search result."""

    id: int
    title: str
    year: Optional[str]

    @classmethod
    def from_dict(cls, payload: Any) -> "TVDBSeries":
        data = _coerce_payload(payload)

        translation_name: Optional[str] = None
        translations = data.get("translations")
        if isinstance(translations, list):
            for item in translations:
                item_dict = _coerce_payload(item)
                translation_name = item_dict.get("name")
                if translation_name:
                    break
        elif isinstance(translations, dict):
            translation_name = translations.get("name")

        name = (
            data.get("name")
            or data.get("seriesName")
            or translation_name
            or data.get("slug")
            or ""
        )

        year_value: Optional[str] = None
        first_aired = data.get("firstAired") or data.get("year") or data.get("firstAiredAt")
        if isinstance(first_aired, str) and first_aired:
            year_value = first_aired.split("-", 1)[0]
        elif isinstance(first_aired, int):
            year_value = str(first_aired)

        logger.debug(
            "Parsed TVDB series payload with id=%s name='%s' year=%s",
            data.get("id"),
            name,
            year_value,
        )

        return cls(
            id=data.get("id") or 0,
            title=name,
            year=year_value if year_value else None,
        )

    def display_text(self) -> str:
        if self.year:
            return f"{self.title} ({self.year})"
        return self.title


class TheTVDBClient:
    """Wrapper around the official ``tvdb_v4_official`` client."""

    _CLIENT_CANDIDATES = ("TVDB", "TvdbV4", "TheTVDB", "Client")

    def __init__(self, *, api_key: str, pin: Optional[str] = None) -> None:
        if not api_key:
            raise ValueError("A TheTVDB API key must be provided.")

        try:
            tvdb_module = importlib.import_module("tvdb_v4_official")
        except ImportError as exc:  # pragma: no cover - runtime dependency guard
            raise RuntimeError(
                "The 'tvdb_v4_official' package is required. Install it via 'pip install tvdb_v4_official'."
            ) from exc

        self._client = self._initialise_client(tvdb_module, api_key, pin)
        self._api_key = api_key
        self._pin = pin

    def _initialise_client(self, module: Any, api_key: str, pin: Optional[str]) -> Any:
        errors: list[str] = []
        for attr in self._CLIENT_CANDIDATES:
            cls = getattr(module, attr, None)
            if cls is None or not inspect.isclass(cls):
                continue

            try:
                return self._instantiate_client(cls, api_key, pin)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            except TypeError as exc:
                errors.append(str(exc))
                continue
        raise RuntimeError(
            "Unable to find a compatible TVDB client implementation in 'tvdb_v4_official'. "
            "Tried: " + ", ".join(self._CLIENT_CANDIDATES) + (f". Errors: {'; '.join(errors)}" if errors else "")
        )

    def _instantiate_client(self, cls: type, api_key: str, pin: Optional[str]) -> Any:
        try:
            signature = inspect.signature(cls)
        except (TypeError, ValueError):  # pragma: no cover - C extension / builtin signature
            signature = None

        if signature is not None:
            kwargs: dict[str, Any] = {}
            requires_pin = False
            for name, parameter in signature.parameters.items():
                normalized = name.lower()
                if normalized in {"api_key", "apikey", "apikeyid", "key"}:
                    kwargs[name] = api_key
                elif normalized in {"pin", "userpin", "user_pin", "userkey", "user_key"}:
                    if pin is None and parameter.default is inspect._empty:
                        requires_pin = True
                    elif pin is not None:
                        kwargs[name] = pin
                elif parameter.default is inspect._empty and parameter.kind in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                ):
                    # Required argument we do not know how to populate.
                    raise TypeError(
                        f"Cannot instantiate {cls.__name__}: required argument '{name}' is not supported."
                    )

            if requires_pin:
                raise ValueError("TheTVDB client requires a PIN. Update your settings to include a valid PIN.")

            try:
                return cls(**kwargs)
            except TypeError:
                # Fall back to positional attempts below.
                pass

        # Attempt a few positional/keyword combinations for older releases.
        attempts: list[tuple[tuple[Any, ...], dict[str, Any]]] = [
            ((api_key,), {}),
            ((api_key, pin), {}) if pin is not None else None,
            ((), {"api_key": api_key}),
            ((), {"api_key": api_key, "pin": pin}) if pin is not None else None,
            ((), {"apikey": api_key}),
            ((), {"apikey": api_key, "pin": pin}) if pin is not None else None,
            ((), {"apiKey": api_key}),
            ((), {"apiKey": api_key, "pin": pin}) if pin is not None else None,
        ]
        for attempt in attempts:
            if attempt is None:
                continue
            args, kwargs = attempt
            kwargs = {key: value for key, value in kwargs.items() if value is not None}
            try:
                return cls(*args, **kwargs)
            except TypeError:
                continue

        raise TypeError(f"Unable to construct {cls.__name__} with the available API key/PIN parameters.")

    def search(self, query: str, *, limit: int = 10) -> List[TVDBSeries]:
        """Search for series on TheTVDB matching ``query``."""

        if not query.strip():
            logger.debug("Ignoring blank search query for TheTVDB lookup")
            return []

        normalized_limit = min(max(limit, 1), 50)
        logger.debug(
            "Requesting TVDB search for query='%s' with limit=%d",
            query,
            normalized_limit,
        )

        raw_results = self._perform_search(query, normalized_limit)
        series_list = [TVDBSeries.from_dict(item) for item in raw_results]
        logger.debug("TVDB query '%s' returned %d result(s)", query, len(series_list))
        return series_list[:normalized_limit]

    def _perform_search(self, query: str, limit: int) -> Iterable[Any]:
        search_callables = self._locate_search_callables()
        if not search_callables:
            raise RuntimeError(
                "The installed 'tvdb_v4_official' client does not expose a recognised search interface."
            )

        last_error: Optional[Exception] = None
        for candidate in search_callables:
            try:
                result = self._invoke_search(candidate, query, limit)
            except TypeError as exc:
                last_error = exc
                continue
            except Exception:
                raise
            else:
                return self._extract_results(result)

        if last_error is not None:
            raise RuntimeError(f"Unable to invoke TheTVDB search endpoint: {last_error}")
        raise RuntimeError("Unable to invoke TheTVDB search endpoint with any known call signature.")

    def _locate_search_callables(self) -> List[Any]:
        """Return a list of callables that can execute a series search."""

        callables: List[Any] = []
        search_attr = getattr(self._client, "search", None)
        if callable(search_attr):
            callables.append(search_attr)
        elif search_attr is not None:
            for name in ("series", "series_search", "seriesSearch"):
                method = getattr(search_attr, name, None)
                if callable(method):
                    callables.append(method)

        for name in ("search_series", "searchSeries", "series_search", "seriesSearch"):
            method = getattr(self._client, name, None)
            if callable(method):
                callables.append(method)

        unique_callables: list[Any] = []
        seen_ids: set[int] = set()
        for func in callables:
            func_id = id(func)
            if func_id not in seen_ids:
                unique_callables.append(func)
                seen_ids.add(func_id)
        return unique_callables

    def _invoke_search(self, func: Any, query: str, limit: int) -> Any:
        """Try calling ``func`` with several common signatures."""

        attempts: list[tuple[tuple[Any, ...], dict[str, Any]]] = [
            ((query,), {}),
            ((query,), {"limit": limit}),
            ((), {"query": query, "limit": limit}),
            ((), {"query": query, "type": "series", "limit": limit}),
            ((), {"q": query, "type": "series", "limit": limit}),
            ((), {"name": query, "limit": limit}),
            ((query, "series"), {"limit": limit}),
            (("series", query), {"limit": limit}),
            ((query,), {"type": "series"}),
            ((query, limit), {}),
        ]

        for args, kwargs in attempts:
            kwargs = {key: value for key, value in kwargs.items() if value is not None}
            try:
                return func(*args, **kwargs)
            except TypeError:
                continue

        raise TypeError("The provided TVDB search callable did not accept any recognised signature.")

    def _extract_results(self, payload: Any) -> Iterable[Any]:
        """Normalise ``payload`` into an iterable of result objects."""

        if payload is None:
            return []
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                return data
            if data is not None:
                return [data]
            return payload.get("results", []) or payload.get("series", [])
        if isinstance(payload, list):
            return payload
        if hasattr(payload, "data"):
            data = getattr(payload, "data")
            if isinstance(data, list):
                return data
        if hasattr(payload, "results"):
            data = getattr(payload, "results")
            if isinstance(data, list):
                return data
        if hasattr(payload, "series"):
            data = getattr(payload, "series")
            if isinstance(data, list):
                return data
        if isinstance(payload, Iterable):
            return list(payload)
        return [payload]
