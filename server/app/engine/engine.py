from app.engine.models import ActorMove, GameOver, GameState, InProgress, Move, MovieMove


def play_move(state: InProgress, move: Move) -> GameState:
    if not state.moves:
        return _advance(state, move)

    previous = state.moves[-1]

    if _is_repeat(state.moves, move) or not _is_valid_connection(previous, move):
        return _game_over(state, move)
    return _advance(state, move)


def forfeit(state: InProgress) -> GameOver:
    return _game_over(state, losing_move=None)


def _advance(state: InProgress, move: Move) -> InProgress:
    return InProgress(
        moves=state.moves + [move],
        current_player_index=(state.current_player_index + 1) % state.player_count,
        player_count=state.player_count,
    )


def _is_repeat(chain: list[Move], move: Move) -> bool:
    return any(m.id == move.id and type(m) is type(move) for m in chain)


def _is_valid_connection(previous: Move, move: Move) -> bool:
    if isinstance(previous, ActorMove) and isinstance(move, MovieMove):
        return previous.id in move.cast_ids
    if isinstance(previous, MovieMove) and isinstance(move, ActorMove):
        return move.id in previous.cast_ids
    return False


def _game_over(state: InProgress, losing_move: Move | None) -> GameOver:
    return GameOver(
        winner_index=(state.current_player_index - 1 + state.player_count) % state.player_count,
        chain=list(state.moves),
        losing_move=losing_move,
    )
