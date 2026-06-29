import re

from fastapi.testclient import TestClient


def test_create_room_returns_code_token_and_player_index(client: TestClient) -> None:
    resp = client.post("/rooms", json={"displayName": "Alice"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["playerIndex"] == 0
    assert body["token"]
    assert body["code"]


def test_create_room_code_is_six_char_base32(client: TestClient) -> None:
    resp = client.post("/rooms", json={"displayName": "Alice"})

    code = resp.json()["code"]
    assert re.fullmatch(r"[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{6}", code)
