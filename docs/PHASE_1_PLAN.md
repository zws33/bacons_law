# Phase 1 Implementation Plan — Engine Port

Source of scope: [PYTHON_TS_REWRITE_PLAN.md](PYTHON_TS_REWRITE_PLAN.md#phase-1-engine-port)
Engine spec (authoritative): [GAME_SPEC_V2.md](GAME_SPEC_V2.md)

**Done when:** the ported test suite (TC-01…TC-12) passes under `pytest`, `mypy --strict` is clean, and `ruff` is clean. No network, no Redis, no FastAPI involvement — the engine is pure functions over pure data.

**Audience:** Senior engineer fluent in TypeScript and Kotlin, newer to Python. Python-specific idioms are explained where they differ from what you already know — primarily how Python expresses Kotlin's sealed classes.

---

## What we're porting

The Kotlin `:core` module (`GameState`, `Move`, `GameEngine`) is gone from this branch (`8eb770d`). We are not translating Kotlin line-by-line — `GAME_SPEC_V2.md` is the contract, and it is already written in Python-flavored pseudocode (snake_case, `set[int]`, `Move | None`). This plan turns that spec into real, type-checked Python.

The engine is small: two data families and two functions.

- **Data:** `Move` = `Actor | Movie`; `GameState` = `InProgress | GameOver`.
- **Behavior:** `play_move(state, move) -> GameState` and `forfeit(state) -> GameOver`.

Everything else (rules R1–R10) is logic *inside* `play_move` and `forfeit`.

---

## Python concept: sum types without sealed classes

This is the one genuinely new idea versus the Kotlin port. Everything else (frozen data, pure functions, exhaustive branching) you already do in Kotlin/TS.

Kotlin models `Move` as a **sealed class** with `Move.Actor` / `Move.Movie` subtypes, and the compiler enforces exhaustive `when`. Python has no sealed classes. The idiomatic equivalent is a **union of dataclasses plus a type alias**, discriminated at runtime with `isinstance`:

```python
@dataclass(frozen=True)
class Actor: ...

@dataclass(frozen=True)
class Movie: ...

Move = Actor | Movie          # type alias — the "sealed" set, by convention
```

| Kotlin | Python |
|---|---|
| `sealed class Move` | `Move = Actor | Movie` (type alias over `@dataclass` types) |
| `data class Actor(...) : Move()` | `@dataclass(frozen=True) class Actor` |
| `when (m) { is Actor -> ...; is Movie -> ... }` | `if isinstance(m, Actor): ... elif isinstance(m, Movie): ...` |
| compiler-enforced exhaustiveness | **not** compiler-enforced; mypy narrows types inside `isinstance` blocks but won't fail an inexhaustive match unless you opt in |

`mypy` does **type narrowing** the same way the Kotlin smart-cast does: inside `if isinstance(previous, Movie):`, mypy knows `previous.cast_ids` exists. That gives us most of the safety of a sealed `when` without the language feature.

The "by convention" caveat matters: nothing stops a third subtype from being added later without updating every branch. We accept that — the union has exactly two members, defined in one file, and the engine is the only consumer. If this set grows, revisit.

---

## Design decisions

These are the choices worth fixing before writing code. The engine API is the one **one-way door** here — Phase 3's WebSocket layer will depend on these signatures and types — so they get the scrutiny.

### D1 — Stdlib `dataclasses`, not Pydantic

Phase 1 scope says *pure, dependency-free logic*. Pydantic is a dependency and a serialization/validation concern; the engine has neither. We use `@dataclass(frozen=True)` from the stdlib. Pydantic models for the wire format (REST DTOs, WS messages) arrive in Phase 2/3 at the API boundary, mapping **to** these engine types — the engine never imports them.

**Trade-off:** we'll write a small mapping layer later (Pydantic DTO → engine dataclass) instead of using one type end-to-end. The benefit is a domain core with zero framework coupling, testable in isolation — the same reason `:core` was pure Kotlin.

### D2 — Frozen dataclasses + union type aliases

`frozen=True` makes instances immutable (attribute assignment raises) and gives us value equality for free, which the tests rely on (`result.moves == [TOM_HANKS, CAST_AWAY]`). State transitions return **new** `InProgress`/`GameOver` instances rather than mutating — matching the spec's pure-function framing.

### D3 — Module-level functions, not a `GameEngine` class

The spec interface is literally two free functions:

```
play_move(state: InProgress, move: Move) -> GameState
forfeit(state: InProgress) -> GameOver
```

Kotlin needed a `GameEngine` interface for DI/testability in the Android app. The pure engine here has no dependencies to inject. Module-level functions are the idiomatic Python form and match the spec exactly. Introducing a class/protocol now would be abstraction without a job (cf. [DECISIONS.md](DECISIONS.md) 007). If Phase 3 ever needs to swap engine implementations, a `Protocol` can be added then.

### D4 — Signature order follows GAME_SPEC_V2: `(state, move)`

The old Kotlin refactor doc used `playMove(move, state)`. `GAME_SPEC_V2` — the authoritative spec for *this* branch — uses `play_move(state, move)`. We follow the spec. (Flagging because it's a silent contract difference from the Kotlin docs.)

### D5 — `cast_ids` stays `set[int]` (per spec), with one noted footgun

The spec data model says `cast_ids: set[int]`, and fixtures use set literals (`{1, 2}`). We match it exactly so the validation contract is identical across the Kotlin and Python showcases.

Caveat to be aware of: a `frozen=True` dataclass auto-generates `__hash__`, and hashing a `Movie` would raise `TypeError` because a `set` is unhashable. **The engine never hashes a `Move`** (repeat detection compares `.id` and type, it doesn't put Moves in a set/dict), so this is latent, not a live bug. If a future phase needs `Move` instances as dict keys or set members, switch `cast_ids` to `frozenset[int]` at that point — `x in cast_ids` works identically for both. Not doing it now keeps the field type identical to the spec.

### D6 — Split `models.py` (data) from `engine.py` (logic)

Mirrors the spec's own "Data Model" vs "Rules" sections and keeps each file small. `__init__.py` re-exports both so callers write `from app.engine import play_move, Actor`.

### D7 — Engine does not validate `player_count`

`GAME_SPEC_V2`'s boundary table assigns player-count enforcement to the session layer ("engine supports N ≥ 2"). The engine trusts its inputs and stays pure — no runtime guards on `player_count`, no assertion that `state` is `InProgress` (the type says so; the session layer guarantees it). This keeps R10 (no I/O, pure) honest and avoids defensive code with no caller.

---

## Target file layout

```
server/app/engine/
├── __init__.py     # barrel re-export (currently empty)
├── models.py       # Actor, Movie, Move, InProgress, GameOver, GameState  (NEW)
└── engine.py       # play_move, forfeit + private helpers                 (NEW)
server/tests/
└── test_engine.py  # TC-01 … TC-12                                        (NEW)
```

No changes to `pyproject.toml` or CI — Phase 0 already wired `mypy app`, `ruff`, and `pytest` over these paths.

---

## File-by-file

### `server/app/engine/models.py`

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Actor:
    id: int
    display_text: str
    image_path: str | None = None


@dataclass(frozen=True)
class Movie:
    id: int
    display_text: str
    cast_ids: set[int] = field(default_factory=set)
    image_path: str | None = None
    release_year: str | None = None


# The "sealed" set of move types. Discriminate with isinstance.
Move = Actor | Movie


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
GameState = InProgress | GameOver
```

Notes:
- **`field(default_factory=...)`** is required for mutable defaults (`list`, `set`). Writing `moves: list[Move] = []` would raise `ValueError` at class definition — Python's equivalent of the "shared mutable default" trap, but dataclasses reject it outright. `default_factory` is called per-instance.
- `Actor`/`Movie` field order and optionality match the spec's Data Model section exactly. Display/metadata fields default to `None` so a minimal `Actor(id=1, display_text="Tom Hanks")` is valid (as the fixtures use).
- `InProgress` defaults (`moves=[]`, `current_player_index=0`, `player_count=2`) make game start a plain construction: `InProgress()` is a fresh 2-player game. No `start_game` factory needed yet (D7 / no premature abstraction).

### `server/app/engine/engine.py`

```python
from app.engine.models import (
    Actor,
    GameOver,
    GameState,
    InProgress,
    Move,
    Movie,
)


def play_move(state: InProgress, move: Move) -> GameState:
    # R1: the first move has no predecessor — always accepted.
    if not state.moves:
        return _advance(state, move)

    previous = state.moves[-1]

    # R5/R6: repeat takes priority over connection validity. Either failure
    # ends the game with the current player losing.
    if _is_repeat(state.moves, move) or not _is_valid_connection(previous, move):
        return _game_over(state, losing_move=move)

    # R2/R3: valid connection — append and rotate.
    return _advance(state, move)


def forfeit(state: InProgress) -> GameOver:
    # R7: current player loses; no losing move.
    return _game_over(state, losing_move=None)


# --- helpers -------------------------------------------------------------

def _is_repeat(chain: list[Move], move: Move) -> bool:
    # R5: a repeat is a same-id move of the same type already in the chain.
    # type(m) is type(move) keeps Actor/Movie id-collisions distinct (R5/TC-11).
    return any(m.id == move.id and type(m) is type(move) for m in chain)


def _is_valid_connection(previous: Move, move: Move) -> bool:
    # R2: Actor after Movie — actor's id must be in the movie's cast.
    if isinstance(previous, Movie) and isinstance(move, Actor):
        return move.id in previous.cast_ids
    # R3: Movie after Actor — previous actor's id must be in the movie's cast.
    if isinstance(previous, Actor) and isinstance(move, Movie):
        return previous.id in move.cast_ids
    # R4: same-type consecutive is always invalid.
    return False


def _advance(state: InProgress, move: Move) -> InProgress:
    # R9: rotate to the next player, wrapping.
    return InProgress(
        moves=[*state.moves, move],
        current_player_index=(state.current_player_index + 1) % state.player_count,
        player_count=state.player_count,
    )


def _game_over(state: InProgress, losing_move: Move | None) -> GameOver:
    # R8: winner is the previous player — the one who did NOT just lose.
    return GameOver(
        winner_index=(state.current_player_index - 1 + state.player_count)
        % state.player_count,
        chain=list(state.moves),  # R6: chain excludes the losing move
        losing_move=losing_move,
    )
```

Why this shape:
- The whole rule set collapses into one `if` chain in `play_move` plus three tiny helpers. Each helper maps to specific rules (see the mapping table below), which keeps the spec ↔ code correspondence auditable.
- `_is_valid_connection` encodes R2, R3, **and** R4 in one place: the two `isinstance` arms are the only valid shapes; everything else (including Actor-after-Actor and Movie-after-Movie) falls through to `return False`. mypy narrows `previous`/`move` inside each arm, so `.cast_ids` / `.id` access is type-checked.
- `_game_over` is shared by the invalid-move path and `forfeit` — the only difference is `losing_move`, exactly as R6/R7 describe.
- `list(state.moves)` / `[*state.moves, move]` produce fresh lists, preserving immutability of the input state.

### `server/app/engine/__init__.py`

```python
from app.engine.engine import forfeit, play_move
from app.engine.models import (
    Actor,
    GameOver,
    GameState,
    InProgress,
    Move,
    Movie,
)

__all__ = [
    "Actor",
    "GameOver",
    "GameState",
    "InProgress",
    "Move",
    "Movie",
    "forfeit",
    "play_move",
]
```

Lets the API/WS layers (and tests) import from the package root: `from app.engine import play_move, InProgress, Actor`. `__all__` declares the public surface and keeps `ruff` from flagging the re-exports as unused imports.

### `server/tests/test_engine.py`

One test function per spec test case, named for traceability. Fixtures mirror `GAME_SPEC_V2` exactly.

```python
from app.engine import Actor, GameOver, InProgress, Movie, forfeit, play_move

# --- fixtures (from GAME_SPEC_V2) ---------------------------------------
TOM_HANKS = Actor(id=1, display_text="Tom Hanks")
HELEN_HUNT = Actor(id=2, display_text="Helen Hunt")
OUTSIDER = Actor(id=99, display_text="Unknown Actor")

CAST_AWAY = Movie(id=10, display_text="Cast Away", cast_ids={1, 2})
TOY_STORY = Movie(id=20, display_text="Toy Story", cast_ids={1})
UNRELATED = Movie(id=30, display_text="Unrelated", cast_ids={99})


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
    movie_id_10 = Movie(id=10, display_text="Some Movie", cast_ids={10})
    actor_same_id = Actor(id=10, display_text="Actor sharing a movie's id")
    # Only a Movie with id=10 is in the chain; an Actor id=10 is a different
    # entity, so this is NOT a repeat — and 10 in cast_ids makes it a valid link.
    state = InProgress(moves=[movie_id_10], current_player_index=0, player_count=2)
    result = play_move(state, actor_same_id)
    assert isinstance(result, InProgress)
    assert result.moves == [movie_id_10, actor_same_id]

    # Same-type id match IS a repeat.
    actor_id_10 = Actor(id=10, display_text="Some Actor")
    movie_link = Movie(id=20, display_text="Linker", cast_ids={10})
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
```

Notes:
- **TC-11** is implemented as the spec's "cleaner version" (its `state3` case) plus the same-type repeat assertion. The spec's intermediate prose (`state`, `state2`) is exploratory thinking, not three separate cases — one test captures both real assertions.
- The trailing `test_unrelated_fixture_is_referenced` only exists because `UNRELATED` is in the spec fixture block but unused by TC-01…12; without a reference, `ruff` (F401-style unused) and reviewers will flag it. Cleanest is to **drop `UNRELATED` from the fixtures** entirely since no test needs it — I included the guard test as the alternative. Decide at implementation time; dropping it is my recommendation.
- `-> None` on every test is required by `mypy --strict` (no untyped defs).
- Each test asserts `isinstance(result, InProgress | GameOver)` first; this both documents the expected branch and narrows the type so `mypy` accepts the field accesses that follow (e.g. `.winner_index` exists only on `GameOver`).

---

## Rule → code mapping

| Rule | Where implemented |
|---|---|
| R1 — first move always accepted | `play_move` early return on empty `moves` |
| R2 — Actor after Movie valid | `_is_valid_connection` arm 1 |
| R3 — Movie after Actor valid | `_is_valid_connection` arm 2 |
| R4 — same-type consecutive invalid | `_is_valid_connection` fall-through `return False` |
| R5 — repeat detection (same id + same type) | `_is_repeat` |
| R6 — invalid move ends game, repeat priority | `play_move` `if _is_repeat(...) or not _is_valid_connection(...)`, `_game_over` |
| R7 — forfeit ends game, `losing_move=None` | `forfeit` |
| R8 — winner is previous player | `_game_over` winner_index formula |
| R9 — rotation wraps | `_advance` current_player_index formula |
| R10 — no I/O, pure | whole module: no imports beyond `app.engine.models` |

## Test-case → test mapping

| TC | Test function |
|---|---|
| 01 | `test_tc01_valid_movie_move_appends_and_advances` |
| 02 | `test_tc02_valid_actor_move_appends_and_advances` |
| 03 | `test_tc03_movie_not_featuring_previous_actor_ends_game` |
| 04 | `test_tc04_actor_not_in_previous_movie_ends_game` |
| 05 | `test_tc05_repeat_actor_ends_game` |
| 06 | `test_tc06_repeat_movie_ends_game` |
| 07 | `test_tc07_forfeit_current_player_loses_no_losing_move` |
| 08 | `test_tc08_first_move_on_empty_chain_always_accepted` |
| 09 | `test_tc09_actor_after_actor_ends_game` |
| 10 | `test_tc10_movie_after_movie_ends_game` |
| 11 | `test_tc11_cross_type_id_collision_is_not_a_repeat` |
| 12 | `test_tc12_player_rotation_wraps_three_players` |

---

## Verification

Run from `server/`:

```bash
uv run ruff check .        # lint + import order
uv run mypy app            # strict type check — the real friction point of Phase 1
uv run pytest              # expect 12 (or 13) passed
```

Expected pytest output:

```
collected 12 items
tests/test_engine.py ............                                  [100%]
12 passed in 0.0Xs
```

CI (`.github/workflows/ci.yml`) already runs all three over `server/` on PRs to `fullstack-py-ts-rewrite` — no workflow change needed.

---

## Commit sequence

Two commits keep data and behavior reviewable independently and each leaves the tree green (`mypy`/`ruff` pass on data-only too):

1. `feat: add engine domain models (Move, GameState)` — `models.py` + `__init__.py` re-exports
2. `feat: implement game engine play_move/forfeit with spec tests` — `engine.py` + `test_engine.py`

Or squash into one `feat: port game engine to python` if you prefer a single Phase 1 landing.

---

## Risk flags

- **`mypy --strict` narrowing is the main friction.** The union return type of `play_move` means callers must narrow with `isinstance` before touching `GameOver`-only fields — by design, but it will surface in Phase 3 when the WS layer consumes results. The engine itself is clean; the tests prove the narrowing pattern.
- **`set[int]` + `frozen=True` hash footgun** (D5) — latent only. If any later phase needs `Move` as a dict key, switch to `frozenset[int]`.
- **Spec ↔ code drift.** If `GAME_SPEC_V2` changes, the rule-mapping table is the audit surface — update both together. The tests are the executable spec; treat a test edit as a spec change.
- **`UNRELATED` fixture is unused** by TC-01…12. Recommend dropping it rather than carrying a guard test (see test notes).
- **No `player_count` validation** (D7) — if a malformed `InProgress` (count < 2) ever reaches the engine, modular arithmetic won't raise but results are meaningless. That's the session layer's contract to uphold (Phase 3).
```
