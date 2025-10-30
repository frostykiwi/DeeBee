from pathlib import Path
from typing import List

import pytest

from deebee.imdb_client import IMDBMovie
from deebee.renamer import (
    DEFAULT_RENAME_FORMAT_KEY,
    DEFAULT_TV_RENAME_FORMAT_KEY,
    MovieRenamer,
)


class DummyConsole:
    def __init__(self, inputs: List[str] | None = None) -> None:
        self.inputs = inputs or []
        self.printed = []

    def print(self, *args, **kwargs) -> None:
        self.printed.append((args, kwargs))

    def input(self, prompt: str = "") -> str:
        if not self.inputs:
            raise RuntimeError("No more inputs queued.")
        return self.inputs.pop(0)


class DummyClient:
    def __init__(self, movies: List[IMDBMovie]) -> None:
        self._movies = movies
        self.calls = []

    def search(self, query: str, *, limit: int = 10) -> List[IMDBMovie]:
        self.calls.append((query, limit))
        return self._movies


@pytest.fixture
def movie(tmp_path: Path) -> Path:
    file_path = tmp_path / "The.Matrix.1999.mkv"
    file_path.write_text("dummy")
    return file_path


@pytest.fixture
def tv_episode(tmp_path: Path) -> Path:
    file_path = tmp_path / "The.Expanse.S02E03.1080p.mkv"
    file_path.write_text("dummy")
    return file_path


def test_guess_search_query(movie: Path) -> None:
    client = DummyClient([])
    renamer = MovieRenamer(client, console=DummyConsole())
    query = renamer._guess_search_query(movie)
    assert query == "The Matrix 1999"


def test_prepare_search_extracts_episode_numbers(tv_episode: Path) -> None:
    client = DummyClient([])
    renamer = MovieRenamer(client, console=DummyConsole())
    search_info = renamer._prepare_search(tv_episode)
    assert search_info.query == "The Expanse"
    assert search_info.season_number == 2
    assert search_info.episode_number == 3


def test_prepare_search_ignores_year_for_tv_episode(tmp_path: Path) -> None:
    episode_path = tmp_path / "Doctor.Who.2005.S01E01.mkv"
    episode_path.write_text("dummy")

    client = DummyClient([])
    renamer = MovieRenamer(client, console=DummyConsole())

    search_info = renamer._prepare_search(episode_path)

    assert search_info.query == "Doctor Who"
    assert search_info.season_number == 1
    assert search_info.episode_number == 1


def test_process_directory_dry_run(movie: Path) -> None:
    movie_info = IMDBMovie(id="tt0133093", title="The Matrix", year="1999")
    client = DummyClient([movie_info])
    renamer = MovieRenamer(client, console=DummyConsole(["1"]))

    directory = movie.parent
    results = renamer.process_directory(directory, dry_run=True, search_limit=5)

    assert client.calls == [("The Matrix 1999", 5)]
    assert len(results) == 1
    candidate = results[0]
    assert candidate.proposed_filename == "The Matrix.mkv"
    # Ensure dry run did not rename the file.
    assert movie.exists()


@pytest.mark.parametrize(
    "format_key,expected",
    [
        (DEFAULT_RENAME_FORMAT_KEY, "The Matrix.mkv"),
        ("movie_title_year", "The Matrix (1999).mkv"),
    ],
)
def test_process_directory_custom_formats(movie: Path, format_key: str, expected: str) -> None:
    movie_info = IMDBMovie(id="tt0133093", title="The Matrix", year="1999")
    client = DummyClient([movie_info])
    renamer = MovieRenamer(
        client,
        console=DummyConsole(["1"]),
        rename_format=format_key,
    )

    directory = movie.parent
    results = renamer.process_directory(directory, dry_run=True, search_limit=5)

    assert len(results) == 1
    candidate = results[0]
    assert candidate.proposed_filename == expected


def test_missing_year_uses_title_only(movie: Path) -> None:
    movie_info = IMDBMovie(id="tt0133093", title="The Matrix", year=None)
    client = DummyClient([movie_info])
    renamer = MovieRenamer(client, console=DummyConsole(["1"]))

    results = renamer.process_directory(movie.parent, dry_run=True, search_limit=5)

    assert len(results) == 1
    assert results[0].proposed_filename == "The Matrix.mkv"


def test_process_directory_includes_episode_numbers(tv_episode: Path) -> None:
    episode_metadata = IMDBMovie(
        id="tt999",
        title="The Expanse",
        year="2015",
        episode_title="Static",
    )
    client = DummyClient([episode_metadata])
    renamer = MovieRenamer(
        client,
        console=DummyConsole(["1"]),
        media_mode="tv",
    )

    results = renamer.process_directory(tv_episode.parent, dry_run=True, search_limit=5)

    assert client.calls == [("The Expanse", 5)]
    assert len(results) == 1
    assert results[0].proposed_filename == "The Expanse - Static - S02E03.mkv"


def test_show_numbers_format_appends_marker(tv_episode: Path) -> None:
    episode_metadata = IMDBMovie(
        id="tt999",
        title="The Expanse",
        year="2015",
        episode_title="Static",
    )
    client = DummyClient([episode_metadata])
    renamer = MovieRenamer(
        client,
        console=DummyConsole(["1"]),
        rename_format="show_numbers",
        media_mode="tv",
    )

    results = renamer.process_directory(tv_episode.parent, dry_run=True, search_limit=5)

    assert len(results) == 1
    assert results[0].proposed_filename == "The Expanse - S02E03.mkv"


def test_show_episode_format_respects_selection(tv_episode: Path) -> None:
    episode_metadata = IMDBMovie(
        id="tt999",
        title="The Expanse",
        year="2015",
        episode_title="Static",
    )
    client = DummyClient([episode_metadata])
    renamer = MovieRenamer(
        client,
        console=DummyConsole(["1"]),
        rename_format="show_episode",
        media_mode="tv",
    )

    results = renamer.process_directory(tv_episode.parent, dry_run=True, search_limit=5)

    assert len(results) == 1
    assert results[0].proposed_filename == "The Expanse - Static.mkv"


def test_show_only_format_respects_selection(tv_episode: Path) -> None:
    episode_metadata = IMDBMovie(
        id="tt999",
        title="The Expanse",
        year="2015",
        episode_title="Static",
    )
    client = DummyClient([episode_metadata])
    renamer = MovieRenamer(
        client,
        console=DummyConsole(["1"]),
        rename_format="show_only",
        media_mode="tv",
    )

    results = renamer.process_directory(tv_episode.parent, dry_run=True, search_limit=5)

    assert len(results) == 1
    assert results[0].proposed_filename == "The Expanse.mkv"
