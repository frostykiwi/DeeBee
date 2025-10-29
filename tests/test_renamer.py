from pathlib import Path
from typing import List

import pytest

from deebee.imdb_client import IMDBMovie
from deebee.renamer import DEFAULT_RENAME_FORMAT_KEY, MovieRenamer


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


def test_guess_search_query(movie: Path) -> None:
    client = DummyClient([])
    renamer = MovieRenamer(client, console=DummyConsole())
    query = renamer._guess_search_query(movie)
    assert query == "The Matrix 1999"


def test_process_directory_dry_run(movie: Path) -> None:
    movie_info = IMDBMovie(id="tt0133093", title="The Matrix", year="1999")
    client = DummyClient([movie_info])
    renamer = MovieRenamer(client, console=DummyConsole(["1"]))

    directory = movie.parent
    results = renamer.process_directory(directory, dry_run=True, search_limit=5)

    assert client.calls == [("The Matrix 1999", 5)]
    assert len(results) == 1
    candidate = results[0]
    assert candidate.proposed_filename == "The Matrix (1999).mkv"
    # Ensure dry run did not rename the file.
    assert movie.exists()


@pytest.mark.parametrize(
    "format_key,expected",
    [
        (DEFAULT_RENAME_FORMAT_KEY, "The Matrix (1999).mkv"),
        ("title_dash_year", "The Matrix - 1999.mkv"),
        ("year_dash_title", "1999 - The Matrix.mkv"),
        ("title_only", "The Matrix.mkv"),
        ("title_brackets_year", "The Matrix [1999].mkv"),
    ],
)
def test_process_directory_custom_formats(movie: Path, format_key: str, expected: str) -> None:
    movie_info = IMDBMovie(id="tt0133093", title="The Matrix", year="1999")
    client = DummyClient([movie_info])
    renamer = MovieRenamer(client, console=DummyConsole(["1"]), rename_format=format_key)

    directory = movie.parent
    results = renamer.process_directory(directory, dry_run=True, search_limit=5)

    assert len(results) == 1
    assert results[0].proposed_filename == expected


def test_missing_year_uses_title_only(movie: Path) -> None:
    movie_info = IMDBMovie(id="tt0133093", title="The Matrix", year=None)
    client = DummyClient([movie_info])
    renamer = MovieRenamer(client, console=DummyConsole(["1"]))

    results = renamer.process_directory(movie.parent, dry_run=True, search_limit=5)

    assert len(results) == 1
    assert results[0].proposed_filename == "The Matrix.mkv"
