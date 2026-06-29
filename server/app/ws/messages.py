from typing import Annotated, Literal

from pydantic import Field

from app.store import MoveModel
from app.util import CamelModel

# --- client -> server ----------------------------------------------------


class JoinMessage(CamelModel):
    type: Literal["join"] = "join"
    display_name: str


class ResumeMessage(CamelModel):
    type: Literal["resume"] = "resume"
    token: str


class SubmitMoveMessage(CamelModel):
    type: Literal["submit_move"] = "submit_move"
    move: MoveModel  # cast_ids is ignored if a client sends it; server re-fetches (D1)


class ForfeitMessage(CamelModel):
    type: Literal["forfeit"] = "forfeit"


ClientMessage = Annotated[
    JoinMessage | ResumeMessage | SubmitMoveMessage | ForfeitMessage,
    Field(discriminator="type"),
]


# --- server -> client ----------------------------------------------------


class PlayerView(CamelModel):
    index: int
    display_name: str
    connected: bool


class StateView(CamelModel):
    type: Literal["state"] = "state"
    code: str
    phase: Literal["waiting", "playing", "over"]
    players: list[PlayerView]
    moves: list[MoveModel]
    current_player_index: int
    winner_index: int | None = None
    losing_move: MoveModel | None = None


class WelcomeMessage(CamelModel):
    type: Literal["welcome"] = "welcome"
    player_index: int
    token: str | None = None  # present only for a fresh `join`
    state: StateView


class ErrorMessage(CamelModel):
    type: Literal["error"] = "error"
    message: str
    code: str  # machine-readable: "not_your_turn" | "room_full" | "bad_token" | "bad_message"
