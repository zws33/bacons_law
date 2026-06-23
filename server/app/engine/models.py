from dataclasses import dataclass, field


@dataclass(frozen=True)
class ActorMove:
    id: int
    display_text: str
    image_path: str | None = None


@dataclass(frozen=True)
class MovieMove:
    id: int
    display_text: str
    cast_ids: set[int] = field(default_factory=set)
    image_path: str | None = None
    release_year: str | None = None


type Move = ActorMove | MovieMove


@dataclass(frozen=True)
class InProgress:
    moves: list[Move] = field(default_factory=list)
    current_player_index: int = 0
    player_count: int = 2


@dataclass(frozen=True)
class GameOver:
    winner_index: int
    chain: list[Move]
    losing_move: Move | None = None


# Terminal-or-active game state.
type GameState = InProgress | GameOver
