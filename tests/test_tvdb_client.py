"""Tests for TheTVDB client helpers."""
from __future__ import annotations

from typing import Any

from deebee.tvdb_client import TheTVDBClient


def test_invoke_episode_lookup_supports_season_type_argument() -> None:
    """Episode lookups should support callables that require a season type."""

    client = object.__new__(TheTVDBClient)
    captured: dict[str, Any] = {}

    def sentinel(*args: Any, **kwargs: Any) -> dict[str, str]:
        if len(args) == 4:
            series_id, season_type, season_number, episode_number = args
            if season_type == "official":
                captured.update(
                    {
                        "series_id": series_id,
                        "season_type": season_type,
                        "season_number": season_number,
                        "episode_number": episode_number,
                        "kwargs": kwargs,
                    }
                )
                return {"name": "Episode"}
        raise TypeError(f"Unexpected invocation: args={args!r}, kwargs={kwargs!r}")

    result = client._invoke_episode_lookup(sentinel, 1, 2, 3)

    assert result == {"name": "Episode"}
    assert captured == {
        "series_id": 1,
        "season_type": "official",
        "season_number": 2,
        "episode_number": 3,
        "kwargs": {},
    }


def test_invoke_episode_lookup_tries_alternative_signatures() -> None:
    """The helper should continue trying combinations until one succeeds."""

    client = object.__new__(TheTVDBClient)
    attempts: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def sentinel(*args: Any, **kwargs: Any) -> dict[str, str]:
        attempts.append((args, kwargs))
        if kwargs.get("seasonType") == "official":
            return {"name": "Episode"}
        raise TypeError("Unsupported signature")

    result = client._invoke_episode_lookup(sentinel, 4, 5, 6)

    assert result == {"name": "Episode"}
    # Ensure at least one attempt used the camelCase seasonType keyword.
    assert any("seasonType" in kwargs for _, kwargs in attempts)


def test_extract_episode_from_collection_prefers_exact_match() -> None:
    """Collection extraction should return the episode matching the numbers."""

    client = object.__new__(TheTVDBClient)

    payload = {
        "data": {
            "episodes": [
                {"seasonNumber": 2, "number": 3, "name": "Target"},
                {"seasonNumber": 2, "number": 4, "name": "Other"},
            ]
        }
    }

    title = client._extract_episode_from_collection(payload, 2, 3)

    assert title == "Target"


def test_extract_episode_from_collection_falls_back_to_first_entry() -> None:
    """When the API filters results, fall back to the first available title."""

    client = object.__new__(TheTVDBClient)

    payload = {
        "data": {
            "episodes": [
                {"name": "Filtered Title"},
                {"name": "Unused"},
            ]
        }
    }

    title = client._extract_episode_from_collection(payload, 1, 1)

    assert title == "Filtered Title"

