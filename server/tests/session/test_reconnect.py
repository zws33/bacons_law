from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession


def _create_room(client: TestClient, name: str = "Alice") -> tuple[str, str]:
    resp = client.post("/rooms", json={"displayName": name})
    body = resp.json()
    return body["code"], body["token"]


def test_resume_with_creator_token_returns_snapshot(client: TestClient) -> None:
    code, creator_token = _create_room(client)

    # First connection drops without playing.
    with client.websocket_connect(f"/ws/rooms/{code}") as ws:
        ws.send_json({"type": "resume", "token": creator_token})
        ws.receive_json()  # welcome

    # Reconnecting with the same token resumes the same identity, no new token.
    with client.websocket_connect(f"/ws/rooms/{code}") as ws:
        ws.send_json({"type": "resume", "token": creator_token})
        welcome = ws.receive_json()
        assert welcome["type"] == "welcome"
        assert welcome["playerIndex"] == 0
        assert welcome["token"] is None
        assert welcome["state"]["phase"] == "waiting"
        assert [p["displayName"] for p in welcome["state"]["players"]] == ["Alice"]


def test_bad_token_is_rejected(client: TestClient) -> None:
    code, _ = _create_room(client)

    with client.websocket_connect(f"/ws/rooms/{code}") as ws:
        ws.send_json({"type": "resume", "token": "not-a-real-token"})
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["code"] == "bad_token"


def test_third_player_join_is_rejected_as_room_full(client: TestClient) -> None:
    code, creator_token = _create_room(client)

    def _join(ws: WebSocketTestSession, name: str) -> None:
        ws.send_json({"type": "join", "displayName": name})

    with (
        client.websocket_connect(f"/ws/rooms/{code}") as p0,
        client.websocket_connect(f"/ws/rooms/{code}") as p1,
        client.websocket_connect(f"/ws/rooms/{code}") as p2,
    ):
        p0.send_json({"type": "resume", "token": creator_token})
        p0.receive_json()  # welcome
        p0.receive_json()  # state

        _join(p1, "Bob")
        p1.receive_json()  # welcome
        p1.receive_json()  # playing broadcast
        p0.receive_json()  # playing broadcast

        _join(p2, "Carol")
        err = p2.receive_json()
        assert err["type"] == "error"
        assert err["code"] == "room_full"
