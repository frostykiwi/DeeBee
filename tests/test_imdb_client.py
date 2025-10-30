from deebee.imdb_client import IMDBClient


class DummyResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"HTTP {self.status_code}")


class DummySession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        if not self._responses:
            raise RuntimeError("No more responses configured for DummySession")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_search_episode_returns_matching_title():
    session = DummySession(
        [
            DummyResponse(
                {
                    "titles": [
                        {"id": "tt100", "primaryTitle": "The Expanse", "startYear": 2015}
                    ]
                }
            ),
            DummyResponse(
                {
                    "episodes": [
                        {"id": "tt200", "title": "Static", "episodeNumber": 3},
                        {"id": "tt201", "title": "Other", "episodeNumber": 4},
                    ]
                }
            ),
        ]
    )

    client = IMDBClient(session=session)
    results = client.search_episode("The Expanse", 2, 3, limit=5)

    assert len(results) == 1
    episode = results[0]
    assert episode.title == "The Expanse"
    assert episode.episode_title == "Static"
    assert episode.year == "2015"
    assert session.calls[0][0].endswith("/search/titles")
    assert session.calls[1][0].endswith("/titles/tt100/episodes")


def test_search_episode_falls_back_to_first_available():
    session = DummySession(
        [
            DummyResponse(
                {
                    "titles": [
                        {"id": "tt300", "primaryTitle": "Sample", "startYear": 2020}
                    ]
                }
            ),
            DummyResponse(
                {
                    "episodes": [
                        {"id": "tt301", "title": "Approximate", "episodeNumber": 2},
                        {"id": "tt302", "title": "Other", "episodeNumber": 5},
                    ]
                }
            ),
        ]
    )

    client = IMDBClient(session=session)
    results = client.search_episode("Sample", 1, 3, limit=5)

    assert len(results) == 1
    assert results[0].episode_title == "Approximate"


def test_search_episode_respects_limit_for_series_requests():
    session = DummySession(
        [
            DummyResponse(
                {
                    "titles": [
                        {"id": "tt400", "primaryTitle": "Series A", "startYear": 2010},
                        {"id": "tt401", "primaryTitle": "Series B", "startYear": 2011},
                    ]
                }
            ),
            DummyResponse(
                {"episodes": [{"id": "tt500", "title": "Found", "episodeNumber": 3}]}
            ),
        ]
    )

    client = IMDBClient(session=session)
    results = client.search_episode("Series", 1, 3, limit=1)

    assert len(results) == 1
    # Only the first series should trigger an episode request because the limit was reached.
    assert len(session.calls) == 2
    assert session.calls[1][0].endswith("/titles/tt400/episodes")
