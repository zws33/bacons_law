"""Full gameplay loop over the WebSocket.

The FakeTmdbClient returns ``cast_ids=[819, 287]`` for every movie, so any movie
connects to actors 819/287, and a movie move is always a valid first move.
"""

from typing import Any

from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession


def _create_room(client: TestClient, name: str = "Alice") -> tuple[str, str]:
    resp = client.post("/rooms", json={"displayName": name})
    body = resp.json()
    return body["code"], body["token"]


def _start_game(
    client: TestClient, p0: WebSocketTestSession, p1: WebSocketTestSession, creator_token: str
) -> None:
    """Creator resumes, second player joins; drains messages up to phase=playing."""
    p0.send_json({"type": "resume", "token": creator_token})
    p0.receive_json()  # welcome
    p0.receive_json()  # state broadcast (one player, waiting)

    p1.send_json({"type": "join", "displayName": "Bob"})
    p1.receive_json()  # welcome
    p1.receive_json()  # playing broadcast
    p0.receive_json()  # playing broadcast


def _submit(
    sender: WebSocketTestSession, watchers: list[WebSocketTestSession], move: dict[str, Any]
) -> dict[str, Any]:
    """Submit a move; every connected socket (sender included) gets the broadcast."""
    sender.send_json({"type": "submit_move", "move": move})
    state = sender.receive_json()
    for w in watchers:
        w.receive_json()
    return state


def _movie(id: int) -> dict[str, Any]:
    return {"kind": "movie", "id": id, "displayText": f"Movie {id}"}


def _actor(id: int) -> dict[str, Any]:
    return {"kind": "actor", "id": id, "displayText": f"Actor {id}"}


def test_two_players_transition_waiting_to_playing(client: TestClient) -> None:
    code, creator_token = _create_room(client)
    with (
        client.websocket_connect(f"/ws/rooms/{code}") as p0,
        client.websocket_connect(f"/ws/rooms/{code}") as p1,
    ):
        p0.send_json({"type": "resume", "token": creator_token})
        w0 = p0.receive_json()
        assert w0["type"] == "welcome"
        assert w0["playerIndex"] == 0
        assert w0["token"] is None  # resume issues no new token
        assert p0.receive_json()["phase"] == "waiting"

        p1.send_json({"type": "join", "displayName": "Bob"})
        w1 = p1.receive_json()
        assert w1["playerIndex"] == 1
        assert w1["token"]  # fresh token for the joiner
        assert p1.receive_json()["phase"] == "playing"
        assert p0.receive_json()["phase"] == "playing"


def test_full_valid_game_alternates_turns(client: TestClient) -> None:
    code, creator_token = _create_room(client)
    with (
        client.websocket_connect(f"/ws/rooms/{code}") as p0,
        client.websocket_connect(f"/ws/rooms/{code}") as p1,
    ):
        _start_game(client, p0, p1, creator_token)

        s = _submit(p0, [p1], _movie(550))
        assert s["currentPlayerIndex"] == 1
        assert len(s["moves"]) == 1

        s = _submit(p1, [p0], _actor(819))
        assert s["currentPlayerIndex"] == 0
        assert len(s["moves"]) == 2

        s = _submit(p0, [p1], _movie(551))
        assert s["currentPlayerIndex"] == 1
        assert len(s["moves"]) == 3

        s = _submit(p1, [p0], _actor(287))
        assert s["phase"] == "playing"
        assert s["currentPlayerIndex"] == 0
        assert len(s["moves"]) == 4


def test_invalid_connection_ends_game(client: TestClient) -> None:
    code, creator_token = _create_room(client)
    with (
        client.websocket_connect(f"/ws/rooms/{code}") as p0,
        client.websocket_connect(f"/ws/rooms/{code}") as p1,
    ):
        _start_game(client, p0, p1, creator_token)

        _submit(p0, [p1], _movie(550))
        s = _submit(p1, [p0], _actor(999))  # 999 not in cast {819, 287}

        assert s["phase"] == "over"
        assert s["winnerIndex"] == 0  # the player who made the bad move loses
        assert s["losingMove"]["id"] == 999


def test_repeat_entity_ends_game(client: TestClient) -> None:
    code, creator_token = _create_room(client)
    with (
        client.websocket_connect(f"/ws/rooms/{code}") as p0,
        client.websocket_connect(f"/ws/rooms/{code}") as p1,
    ):
        _start_game(client, p0, p1, creator_token)

        _submit(p0, [p1], _movie(550))
        _submit(p1, [p0], _actor(819))
        s = _submit(p0, [p1], _movie(550))  # reused movie

        assert s["phase"] == "over"
        assert s["winnerIndex"] == 1


def test_move_out_of_turn_is_protocol_error(client: TestClient) -> None:
    code, creator_token = _create_room(client)
    with (
        client.websocket_connect(f"/ws/rooms/{code}") as p0,
        client.websocket_connect(f"/ws/rooms/{code}") as p1,
    ):
        _start_game(client, p0, p1, creator_token)

        # It is player 0's turn; player 1 submits anyway.
        p1.send_json({"type": "submit_move", "move": _movie(550)})
        err = p1.receive_json()
        assert err["type"] == "error"
        assert err["code"] == "not_your_turn"

        # State is untouched: player 0 can still open the game.
        s = _submit(p0, [p1], _movie(550))
        assert s["phase"] == "playing"
        assert len(s["moves"]) == 1


def test_forfeit_ends_game_opponent_wins(client: TestClient) -> None:
    code, creator_token = _create_room(client)
    with (
        client.websocket_connect(f"/ws/rooms/{code}") as p0,
        client.websocket_connect(f"/ws/rooms/{code}") as p1,
    ):
        _start_game(client, p0, p1, creator_token)

        p0.send_json({"type": "forfeit"})
        s = p0.receive_json()
        p1.receive_json()

        assert s["phase"] == "over"
        assert s["winnerIndex"] == 1
        assert s["losingMove"] is None
