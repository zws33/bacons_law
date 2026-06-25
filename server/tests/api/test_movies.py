from fastapi.testclient import TestClient


def test_movie_search_resturns_results(client: TestClient) -> None:
    response = client.get("/movies/search/", params={"query": "fight"})
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["id"] == 550
    assert results[0]["title"] == "Fight Club"


def test_movie_search_response_is_camel_case(client: TestClient) -> None:
    response = client.get("/movies/search/", params={"query": "fight"})
    result = response.json()[0]
    assert "releaseYear" in result
    assert "posterPath" in result
    assert "release_year" not in result
    assert "poster_path" not in result


def test_movie_search_missing_query_returns_422(client: TestClient) -> None:
    response = client.get("/movies/search/")
    assert response.status_code == 422


def test_movie_credits_returns_cast_ids(client: TestClient) -> None:
    response = client.get("/movies/550/credits")
    result = response.json()
    assert "castIds" in result


def test_movie_credits_invalid_id_returns_422(client: TestClient) -> None:
    response = client.get("/movies/abc/credits")
    assert response.status_code == 422
