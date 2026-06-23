from app.engine import ActorMove, GameOver, InProgress, MovieMove, forfeit, play_move

# --- fixtures (from GAME_SPEC_V2) ---------------------------------------
TOM_HANKS = ActorMove(id=1, display_text="Tom Hanks")
HELEN_HUNT = ActorMove(id=2, display_text="Helen Hunt")
OUTSIDER = ActorMove(id=99, display_text="Unknown Actor")

CAST_AWAY = MovieMove(id=10, display_text="Cast Away", cast_ids={1, 2})
TOY_STORY = MovieMove(id=20, display_text="Toy Story", cast_ids={1})
UNRELATED = MovieMove(id=30, display_text="Unrelated", cast_ids={99})


def test_tc01_valid_movie_move_appends_and_advances() -> None:
    state = InProgress(moves=[TOM_HANKS], current_player_index=1, player_count=2)
    result = play_move(state, CAST_AWAY)
    assert isinstance(result, InProgress)
    assert result.moves == [TOM_HANKS, CAST_AWAY]
    assert result.current_player_index == 0


def test_tc02_valid_actor_move_appends_and_advances() -> None:
    state = InProgress(moves=[TOM_HANKS, CAST_AWAY], current_player_index=0, player_count=2)
    result = play_move(state, HELEN_HUNT)
    assert isinstance(result, InProgress)
    assert result.moves == [TOM_HANKS, CAST_AWAY, HELEN_HUNT]
    assert result.current_player_index == 1


def test_tc03_movie_not_featuring_previous_actor_ends_game() -> None:
    state = InProgress(moves=[HELEN_HUNT], current_player_index=0, player_count=2)
    result = play_move(state, TOY_STORY)
    assert isinstance(result, GameOver)
    assert result.winner_index == 1
    assert result.losing_move == TOY_STORY
    assert result.chain == [HELEN_HUNT]


def test_tc04_actor_not_in_previous_movie_ends_game() -> None:
    state = InProgress(moves=[TOM_HANKS, CAST_AWAY], current_player_index=0, player_count=2)
    result = play_move(state, OUTSIDER)
    assert isinstance(result, GameOver)
    assert result.winner_index == 1
    assert result.losing_move == OUTSIDER
    assert result.chain == [TOM_HANKS, CAST_AWAY]


def test_tc05_repeat_actor_ends_game() -> None:
    state = InProgress(
        moves=[TOM_HANKS, CAST_AWAY, HELEN_HUNT], current_player_index=1, player_count=2
    )
    result = play_move(state, TOM_HANKS)
    assert isinstance(result, GameOver)
    assert result.winner_index == 0
    assert result.losing_move == TOM_HANKS
    assert result.chain == [TOM_HANKS, CAST_AWAY, HELEN_HUNT]


def test_tc06_repeat_movie_ends_game() -> None:
    state = InProgress(
        moves=[TOM_HANKS, CAST_AWAY, HELEN_HUNT, TOY_STORY],
        current_player_index=0,
        player_count=2,
    )
    result = play_move(state, CAST_AWAY)
    assert isinstance(result, GameOver)
    assert result.winner_index == 1
    assert result.losing_move == CAST_AWAY
    assert result.chain == [TOM_HANKS, CAST_AWAY, HELEN_HUNT, TOY_STORY]


def test_tc07_forfeit_current_player_loses_no_losing_move() -> None:
    state = InProgress(moves=[TOM_HANKS], current_player_index=1, player_count=2)
    result = forfeit(state)
    assert isinstance(result, GameOver)
    assert result.winner_index == 0
    assert result.losing_move is None
    assert result.chain == [TOM_HANKS]


def test_tc08_first_move_on_empty_chain_always_accepted() -> None:
    state = InProgress(moves=[], current_player_index=0, player_count=2)
    result = play_move(state, TOM_HANKS)
    assert isinstance(result, InProgress)
    assert result.moves == [TOM_HANKS]
    assert result.current_player_index == 1


def test_tc09_actor_after_actor_ends_game() -> None:
    state = InProgress(moves=[TOM_HANKS], current_player_index=1, player_count=2)
    result = play_move(state, HELEN_HUNT)
    assert isinstance(result, GameOver)
    assert result.winner_index == 0
    assert result.losing_move == HELEN_HUNT


def test_tc10_movie_after_movie_ends_game() -> None:
    state = InProgress(moves=[TOM_HANKS, CAST_AWAY], current_player_index=0, player_count=2)
    result = play_move(state, TOY_STORY)
    assert isinstance(result, GameOver)
    assert result.winner_index == 1
    assert result.losing_move == TOY_STORY


def test_tc11_cross_type_id_collision_is_not_a_repeat() -> None:
    movie_id_10 = MovieMove(id=10, display_text="Some Movie", cast_ids={10})
    actor_same_id = ActorMove(id=10, display_text="Actor sharing a movie's id")
    # Only a Movie with id=10 is in the chain; an Actor id=10 is a different
    # entity, so this is NOT a repeat — and 10 in cast_ids makes it a valid link.
    state = InProgress(moves=[movie_id_10], current_player_index=0, player_count=2)
    result = play_move(state, actor_same_id)
    assert isinstance(result, InProgress)
    assert result.moves == [movie_id_10, actor_same_id]

    # Same-type id match IS a repeat.
    actor_id_10 = ActorMove(id=10, display_text="Some Actor")
    movie_link = MovieMove(id=20, display_text="Linker", cast_ids={10})
    repeat_state = InProgress(
        moves=[actor_id_10, movie_link], current_player_index=0, player_count=2
    )
    repeat_result = play_move(repeat_state, actor_id_10)
    assert isinstance(repeat_result, GameOver)
    assert repeat_result.losing_move == actor_id_10


def test_tc12_player_rotation_wraps_three_players() -> None:
    state = InProgress(moves=[TOM_HANKS], current_player_index=2, player_count=3)
    result = play_move(state, CAST_AWAY)
    assert isinstance(result, InProgress)
    assert result.current_player_index == 0  # 2 -> 0 wrap

    forfeited = forfeit(state)
    assert isinstance(forfeited, GameOver)
    assert forfeited.winner_index == 1  # (2 - 1 + 3) % 3


def test_unrelated_fixture_is_referenced() -> None:
    # UNRELATED exists in the spec fixtures; assert its shape so the import
    # isn't dead. (Optional — drop if you prefer not to carry it.)
    assert UNRELATED.cast_ids == {99}
