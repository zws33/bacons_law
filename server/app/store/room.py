from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import Field

from app.engine import ActorMove, GameOver, InProgress, Move, MovieMove
from app.util.camel_model import CamelModel


class ActorMoveModel(CamelModel):
    kind: Literal["actor"] = "actor"
    id: int
    display_text: str
    image_path: str | None = None


class MovieMoveModel(CamelModel):
    kind: Literal["movie"] = "movie"
    id: int
    display_text: str
    cast_ids: set[int] = Field(default_factory=set)
    image_path: str | None = None
    release_year: str | None = None


MoveModel = Annotated[ActorMoveModel | MovieMoveModel, Field(discriminator="kind")]


class Player(CamelModel):
    index: int
    display_name: str
    token: str


class Room(CamelModel):
    code: str
    players: list[Player] = Field(default_factory=list)
    moves: list[MoveModel] = Field(default_factory=list)
    current_player_index: int = 0
    player_count: int = 2
    winner_index: int | None = None
    losing_move: MoveModel | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    ended_at: datetime | None = None

    @property
    def phase(self) -> Literal["waiting", "playing", "over"]:
        if self.ended_at is not None:
            return "over"
        if len(self.players) < self.player_count:
            return "waiting"
        return "playing"


# helpers


def _to_domain_model(move: MoveModel) -> Move:
    if move.kind == "actor":
        return ActorMove(id=move.id, display_text=move.display_text, image_path=move.image_path)
    return MovieMove(
        id=move.id,
        display_text=move.display_text,
        image_path=move.image_path,
        cast_ids=set(move.cast_ids),
        release_year=move.release_year,
    )


def _from_domain_model(model: Move) -> MoveModel:
    if isinstance(model, ActorMove):
        return ActorMoveModel(
            id=model.id, display_text=model.display_text, image_path=model.image_path
        )
    else:
        return MovieMoveModel(
            id=model.id,
            display_text=model.display_text,
            cast_ids=set(model.cast_ids),
            image_path=model.image_path,
            release_year=model.release_year,
        )


def to_engine_state(room: Room) -> InProgress:
    return InProgress(
        moves=[_to_domain_model(m) for m in room.moves],
        current_player_index=room.current_player_index,
        player_count=room.player_count,
    )


def apply_in_progress(room: Room, state: InProgress) -> Room:
    return room.model_copy(
        update={
            "moves": [_from_domain_model(model=m) for m in state.moves],
            "current_player_index": state.current_player_index,
        }
    )


def apply_game_over(room: Room, state: GameOver) -> Room:
    return room.model_copy(
        update={
            "winner_index": state.winner_index,
            "losing_move": _from_domain_model(state.losing_move) if state.losing_move else None,
            "ended_at": datetime.now(UTC),
        }
    )
