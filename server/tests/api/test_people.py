from fastapi.testclient import TestClient


def test_people_search_returns_results(client: TestClient) -> None:
    response = client.get("/people/search", params={"query": "brad"})
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["id"] == 819
    assert results[0]["name"] == "Brad Pitt"


def test_people_search_response_is_camel_case(client: TestClient) -> None:
    response = client.get("/people/search", params={"query": "brad"})
    result = response.json()[0]
    assert "profilePath" in result
    assert "profile_path" not in result


def test_people_search_missing_query_returns_422(client: TestClient) -> None:
    response = client.get("/people/search")
    assert response.status_code == 422
