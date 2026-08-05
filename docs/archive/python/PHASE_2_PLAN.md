# Phase 2 Implementation Plan — TMDB REST Proxy

Source of scope: [PYTHON_TS_REWRITE_PLAN.md](PYTHON_TS_REWRITE_PLAN.md#phase-2-tmdb-rest-proxy)
Wire contract reference (Kotlin backend): `git show main:backend/src/main/java/me/zwsmith/backend/`

**Done when:** `GET /movies/search`, `GET /people/search`, and `GET /movies/{id}/credits` return correctly shaped responses against real TMDB data, and the test suite passes with a mocked TMDB client — no real HTTP calls in tests. `mypy --strict` and `ruff` are clean.

---

## What we're building

The Kotlin `:backend` was a thin TMDB proxy: normalize TMDB's wire format into domain-shaped responses, keep the API key server-side. Phase 2 is the same job, different runtime. The three endpoints and their response shapes are already defined by what the old backend shipped; this plan reproduces that contract exactly so Phase 4's React client has a stable target.

The engine (Phase 1) is pure logic with no framework involvement. Phase 2 is the first code that touches FastAPI directly: routing, serialization, dependency injection, and a real HTTP client to TMDB.

---

## FastAPI concepts: what's new this phase

### Dependency injection via `Depends`

FastAPI's DI works at the function signature level. You declare what a route needs; FastAPI resolves and provides it before each request:

```python
@router.get("/movies/search")
async def search_movies(
    query: str,
    tmdb: TmdbClient = Depends(get_tmdb_client),
) -> list[MovieSearchResult]:
    return await tmdb.search_movies(query)
```

`get_tmdb_client` is a callable FastAPI invokes per request. It reads the real client from `app.state`. In tests, the whole function is replaced via `app.dependency_overrides`:

```python
app.dependency_overrides[get_tmdb_client] = lambda: FakeTmdbClient()
```

For a TypeScript engineer, this is analogous to NestJS's `@Injectable()` / module-level provider pattern. For a Kotlin/Ktor engineer, it's similar to threading a dependency through `ApplicationCall` parameters, except FastAPI resolves the graph automatically.

### `Protocol` for structural subtyping

Python's `Protocol` (from `typing`) is the equivalent of a TypeScript interface or Kotlin interface for structural typing:

```python
class TmdbClient(Protocol):
    async def search_movies(self, query: str) -> list[MovieSearchResult]: ...
```

Any class with a compatible signature satisfies `TmdbClient` — no explicit declaration needed. `HttpxTmdbClient` and `FakeTmdbClient` both satisfy this protocol without inheriting from it.

| Kotlin                         | Python                                            |
| ------------------------------ | ------------------------------------------------- |
| `interface TmdbClient`         | `class TmdbClient(Protocol)`                      |
| `class HttpxImpl : TmdbClient` | `class HttpxTmdbClient` (structurally compatible) |
| compiler-verified              | mypy-verified via type annotations                |

mypy verifies Protocol compatibility when you annotate the assignment: `tmdb: TmdbClient = HttpxTmdbClient(...)`. Inside the annotation, mypy checks that all Protocol methods are present with matching signatures.

---

## Design decisions

### D1 — Pydantic for API response models; engine dataclasses stay pure

Phase 1 used stdlib `@dataclass(frozen=True)` for engine types — zero framework dependency. API responses have different requirements: JSON serialization with field renaming, OpenAPI schema generation, optional field defaults. Pydantic is the right tool for both, and it is already a FastAPI dependency.

Two distinct model layers:

- **Engine models** (`app/engine/models.py`) — immutable domain types, stdlib dataclasses, no framework imports. These never cross the API boundary.
- **API response models** (`app/models/tmdb.py`) — Pydantic `BaseModel`, serialization-aware, API boundary only.

Routes populate API models from raw TMDB JSON. Engine dataclasses enter the picture in Phase 3, when the session layer constructs `MovieMove` from a `MovieCreditsResult`. That mapping belongs in the session layer — not here.

### D2 — camelCase JSON output to match Kotlin contract

The Kotlin backend's wire format uses camelCase field names: `releaseYear`, `posterPath`, `castIds`, `profilePath`. Phase 4's React client will be built against this contract. We match it exactly.

Pydantic v2's `alias_generator=to_camel` plus `populate_by_name=True` handles the mapping: Python fields are snake_case (idiomatic), JSON output is camelCase (wire contract). FastAPI serializes response models by alias when `response_model` is inferred from the return type annotation.

The camelCase contract is verified by two dedicated tests (`test_*_response_uses_camel_case`) — if Pydantic alias configuration is wrong, those tests catch it before Phase 4 depends on the shape.

### D3 — `TmdbClient` Protocol + `Depends` for testability

The "done when" criterion requires tests with a mocked TMDB client. FastAPI's `app.dependency_overrides` is the standard mechanism: tests replace `get_tmdb_client` with a lambda that returns a `FakeTmdbClient`. Routes need no test-specific code paths.

The `TmdbClient` Protocol is the shared contract. mypy verifies that both `HttpxTmdbClient` and `FakeTmdbClient` implement it via the type annotations on their usages.

### D4 — `httpx.AsyncClient` for TMDB HTTP calls

FastAPI is async-native; TMDB calls are I/O-bound. `httpx.AsyncClient` is the standard async HTTP client in the FastAPI ecosystem (it is also what `TestClient` wraps internally). Using a sync HTTP client blocks the event loop per TMDB request.

**pyproject.toml change needed:** move `httpx2` from dev dependencies to production dependencies (or add it to both). It is currently dev-only; the TMDB client needs it at runtime, not just in tests.

### D5 — TMDB key from environment, read at startup, fail fast if absent

`os.environ["TMDB_API_KEY"]` in FastAPI's lifespan context — not per-request. Raises `KeyError` at startup if absent. This matches the Kotlin backend's `System.getenv("TMDB_API_KEY") ?: error(...)` behavior and prevents serving broken responses from a misconfigured deployment.

The key is held inside `HttpxTmdbClient`, never passed through route handlers and never logged.

**Test implication:** `TestClient` triggers the lifespan, which reads `TMDB_API_KEY`. Without the env var, all tests fail with `KeyError`. The fix: add `os.environ.setdefault("TMDB_API_KEY", "test-key-placeholder")` to `tests/conftest.py` (top-level, before any `app` import). `FakeTmdbClient` + `dependency_overrides` ensure the placeholder is never used in a real HTTP call.

### D6 — `httpx.AsyncClient` lifecycle owned by the lifespan

The `httpx.AsyncClient` is created once in the lifespan and closed on shutdown. Creating one per request is wasteful (no connection pool reuse) and leaks file descriptors. Creating one at module level means it outlives FastAPI's lifecycle management.

The lifespan holds `HttpxTmdbClient` as its concrete type (not `TmdbClient`) so `aclose()` — a lifecycle concern, not a business method — type-checks without polluting the Protocol.

### D7 — Routers split by domain, assembled in `api/__init__.py`

`movies.py` owns `/movies/*`; `people.py` owns `/people/*`. Each file defines one `APIRouter` with a `prefix`. `app/api/__init__.py` assembles them into a single router mounted in `main.py`. Mirrors the Kotlin backend's `moviesRoutes` / `peopleRoutes` split.

### D8 — Let FastAPI validate path and query parameters; no manual parsing

`movie_id: int` in the path — FastAPI coerces and validates. `GET /movies/abc/credits` returns 422 automatically. This replaces Kotlin's explicit `call.parameters["id"]?.toIntOrNull() ?: return@get call.respond(BadRequest, ...)`.

`query: str` as a function parameter (no path marker) — FastAPI treats it as a required query parameter. Missing `query` returns 422 automatically, no guard code needed.

### D9 — Page 1 only; no pagination parameter

TMDB search results are paginated. This proxy returns page 1 only — no `page` query parameter support. The Kotlin backend had the same scope. This is a deliberate decision, not an oversight; call it out in route docstrings if Phase 4 surfaces it as a gap.

### D10 — Pass TMDB errors upstream; no error absorption

`httpx` raises `httpx.HTTPStatusError` via `.raise_for_status()` on non-2xx responses. FastAPI's default handler returns 500 for unhandled exceptions, which callers can treat as 502 from a proxy. Absorbing errors by returning empty lists hides failures — Phase 3 and 4 need real error signal to display meaningful UI states.

Finer-grained error mapping (TMDB 404 → proxy 404, TMDB 401 → proxy 503) is Phase 3 work if Phase 4 needs it.

---

## Target file layout

```
server/app/
├── api/
│   ├── __init__.py         # update: router assembly (was empty)
│   ├── movies.py           # NEW: GET /movies/search, GET /movies/{id}/credits
│   └── people.py           # NEW: GET /people/search
├── models/
│   ├── __init__.py         # update: re-export response models (was empty)
│   └── tmdb.py             # NEW: Pydantic response DTOs
├── deps.py                 # NEW: get_tmdb_client dependency function
├── tmdb_client.py          # NEW: TmdbClient Protocol + HttpxTmdbClient
└── main.py                 # update: lifespan + mount api router

server/tests/
├── conftest.py             # NEW: set TMDB_API_KEY env var before app import
└── api/
    ├── __init__.py         # NEW
    ├── conftest.py         # NEW: FakeTmdbClient + client fixture
    ├── test_movies.py      # NEW: movie endpoint integration tests
    └── test_people.py      # NEW: people endpoint integration tests
```

`pyproject.toml`: add `httpx` to `[project].dependencies`.

No new packages required — Pydantic is already a FastAPI transitive dependency. `httpx` is the only production addition.

---

## File-by-file

### `server/app/models/tmdb.py`

```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class MovieSearchResult(_CamelModel):
    id: int
    title: str
    release_year: str | None = None
    poster_path: str | None = None


class PersonSearchResult(_CamelModel):
    id: int
    name: str
    profile_path: str | None = None


class MovieCreditsResult(_CamelModel):
    id: int
    cast_ids: list[int]
```

Notes:

- `_CamelModel` is a private base — the `_` prefix signals it is not part of the module's public surface. `app/models/__init__.py` re-exports only the three concrete models.
- `alias_generator=to_camel` maps Python snake_case fields to camelCase JSON keys on serialization: `release_year` → `"releaseYear"`, `cast_ids` → `"castIds"`, `poster_path` → `"posterPath"`, `profile_path` → `"profilePath"`. `populate_by_name=True` means code can construct models by Python field name (as all internal code does) while the JSON output still uses the alias.
- `MovieCreditsResult.cast_ids` is `list[int]` (ordered), not `set[int]` (the engine's type). TMDB returns an ordered cast list; preserving order is free and potentially useful to callers. When Phase 3 constructs an engine `MovieMove` from this response, the session layer converts `cast_ids` to `set[int]` at that boundary — the mapping belongs there, not in the proxy model.

### `server/app/tmdb_client.py`

```python
from typing import Protocol

import httpx

from app.models.tmdb import MovieCreditsResult, MovieSearchResult, PersonSearchResult

_TMDB_BASE = "https://api.themoviedb.org/3"


class TmdbClient(Protocol):
    async def search_movies(self, query: str) -> list[MovieSearchResult]: ...
    async def search_people(self, query: str) -> list[PersonSearchResult]: ...
    async def get_movie_credits(self, movie_id: int) -> MovieCreditsResult: ...


class HttpxTmdbClient:
    def __init__(self, api_key: str, http_client: httpx.AsyncClient) -> None:
        self._api_key = api_key
        self._http = http_client

    async def search_movies(self, query: str) -> list[MovieSearchResult]:
        r = await self._http.get(
            f"{_TMDB_BASE}/search/movie",
            params={"query": query, "api_key": self._api_key},
        )
        r.raise_for_status()
        return [
            MovieSearchResult(
                id=m["id"],
                title=m["title"],
                release_year=(m.get("release_date") or "")[:4] or None,
                poster_path=m.get("poster_path"),
            )
            for m in r.json()["results"]
        ]

    async def search_people(self, query: str) -> list[PersonSearchResult]:
        r = await self._http.get(
            f"{_TMDB_BASE}/search/person",
            params={"query": query, "api_key": self._api_key},
        )
        r.raise_for_status()
        return [
            PersonSearchResult(
                id=p["id"],
                name=p["name"],
                profile_path=p.get("profile_path"),
            )
            for p in r.json()["results"]
        ]

    async def get_movie_credits(self, movie_id: int) -> MovieCreditsResult:
        r = await self._http.get(
            f"{_TMDB_BASE}/movie/{movie_id}/credits",
            params={"api_key": self._api_key},
        )
        r.raise_for_status()
        data = r.json()
        return MovieCreditsResult(
            id=data["id"],
            cast_ids=[c["id"] for c in data["cast"]],
        )

    async def aclose(self) -> None:
        await self._http.aclose()
```

Notes:

- `httpx.AsyncClient` is injected rather than constructed inside the class. This keeps the lifecycle in one place (the lifespan in `main.py`) and makes `HttpxTmdbClient` easier to swap during testing if a lower-level HTTP mock is ever needed.
- `release_year` extraction: TMDB returns `"release_date"` as `"YYYY-MM-DD"`, `""`, or `null`/missing. `(m.get("release_date") or "")[:4] or None` handles all three: `or ""` converts `None` to the empty string before slicing (avoiding `TypeError`); the trailing `or None` converts an empty-year slice back to `None`. The Kotlin equivalent used `it.release_date?.take(4)`.
- `r.raise_for_status()` propagates non-2xx TMDB responses as `httpx.HTTPStatusError` (D10).
- `aclose()` follows `httpx.AsyncClient`'s naming convention. It is not part of the `TmdbClient` Protocol — it is a lifecycle concern, not a business method. The lifespan (which holds the concrete `HttpxTmdbClient` type) calls it directly.

### `server/app/deps.py`

```python
from fastapi import Request

from app.tmdb_client import TmdbClient


def get_tmdb_client(request: Request) -> TmdbClient:
    client: TmdbClient = request.app.state.tmdb_client
    return client
```

Notes:

- One function, one file. Tests import `get_tmdb_client` from here to register overrides:
  `app.dependency_overrides[get_tmdb_client] = lambda: FakeTmdbClient()`.
- `app.state` is typed as `Any`; the explicit annotation `client: TmdbClient = ...` is the bridge that makes mypy treat the return value as `TmdbClient`. This is intentional — `app.state` is a dynamic bag; the annotation here is the one place that pins the type contract.
- The override lambda `lambda: FakeTmdbClient()` takes no parameters. FastAPI's DI system inspects the override's signature and injects only the parameters it declares — a zero-arg lambda is valid and skips `Request` injection entirely.

### `server/app/api/movies.py`

```python
from fastapi import APIRouter, Depends

from app.deps import get_tmdb_client
from app.models.tmdb import MovieCreditsResult, MovieSearchResult
from app.tmdb_client import TmdbClient

router = APIRouter(prefix="/movies")


@router.get("/search")
async def search_movies(
    query: str,
    tmdb: TmdbClient = Depends(get_tmdb_client),
) -> list[MovieSearchResult]:
    return await tmdb.search_movies(query)


@router.get("/{movie_id}/credits")
async def get_movie_credits(
    movie_id: int,
    tmdb: TmdbClient = Depends(get_tmdb_client),
) -> MovieCreditsResult:
    return await tmdb.get_movie_credits(movie_id)
```

Notes:

- `query: str` without `Query(...)` — FastAPI infers it as a required query parameter. Missing `query` returns 422 (D8).
- `movie_id: int` in the path — FastAPI coerces and validates. `GET /movies/abc/credits` returns 422; no manual parsing (D8).
- No explicit `response_model=` — FastAPI infers it from the return type annotation. The return type annotation also drives OpenAPI schema generation.
- `tmdb: TmdbClient = Depends(get_tmdb_client)` — the explicit `TmdbClient` type annotation is what lets mypy type-check the route body (`tmdb.search_movies(...)` is known to return `list[MovieSearchResult]`). Without the annotation, `tmdb` would be inferred as `Any` under `--strict`.

### `server/app/api/people.py`

````python
from fastapi import APIRouter, Depends

from app.deps import get_tmdb_client
from app.models.tmdb import PersonSearchResult
from app.tmdb_client import TmdbClient

router = APIRouter(prefix="/people")


@router.get("/search")
async def search_people(
    query: str,
    tmdb: TmdbClient = Depends(get_tmdb_client),
) -> list[PersonSearchResult]:
    return await tmdb.search_people(query) ```

### `server/app/api/__init__.py`

```python
from fastapi import APIRouter

from app.api.movies import router as movies_router
from app.api.people import router as people_router

router = APIRouter()
router.include_router(movies_router)
router.include_router(people_router)
````

### `server/app/main.py` (updated)

```python
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.api import router
from app.tmdb_client import HttpxTmdbClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    api_key = os.environ["TMDB_API_KEY"]
    tmdb = HttpxTmdbClient(api_key, httpx.AsyncClient())
    app.state.tmdb_client = tmdb
    yield
    await tmdb.aclose()


app = FastAPI(lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

Notes:

- `AsyncGenerator[None, None]` is the correct mypy return type for an `@asynccontextmanager` lifespan function under `--strict`. The first `None` is the yield type; the second is the send type.
- `tmdb` is `HttpxTmdbClient` (concrete type), not `TmdbClient`. The lifespan needs `aclose()`, which is not on the Protocol. Keeping the concrete type here is intentional (D6).
- `app.state.tmdb_client = tmdb` stores the client for `get_tmdb_client` to retrieve. `app.state` is `Any`, so no cast is needed.
- `TmdbClient` is not imported here — `main.py` only needs the concrete class. The Protocol lives in `tmdb_client.py` and is consumed by routes and `deps.py`.

### `server/tests/conftest.py` (new)

```python
import os

os.environ.setdefault("TMDB_API_KEY", "test-key-placeholder")
```

This must be at the top of `conftest.py`, before any `app.*` import. pytest loads `conftest.py` before test collection, so the env var is set before the lifespan reads it. `setdefault` is a no-op if the real key is already in the environment (e.g., in CI with the secret set), so this does not interfere with integration tests run against real TMDB.

### `server/tests/api/conftest.py` (new)

```python
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.deps import get_tmdb_client
from app.main import app
from app.models.tmdb import MovieCreditsResult, MovieSearchResult, PersonSearchResult


class FakeTmdbClient:
    async def search_movies(self, query: str) -> list[MovieSearchResult]:
        return [MovieSearchResult(id=550, title="Fight Club", release_year="1999")]

    async def search_people(self, query: str) -> list[PersonSearchResult]:
        return [PersonSearchResult(id=819, name="Brad Pitt")]

    async def get_movie_credits(self, movie_id: int) -> MovieCreditsResult:
        return MovieCreditsResult(id=movie_id, cast_ids=[819, 287])


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_tmdb_client] = lambda: FakeTmdbClient()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

Notes:

- `FakeTmdbClient` implements all three Protocol methods. mypy verifies this structurally — if the Protocol ever gains a method, mypy flags the missing implementation in `FakeTmdbClient`.
- The fixture is scoped to `tests/api/` only (not engine tests). `tests/engine/` has no `client` fixture and no dependency on `app.main`.
- `app.dependency_overrides.clear()` after each test prevents override leakage between test functions.
- `with TestClient(app) as c:` triggers the lifespan (startup + teardown). The lifespan creates a real `HttpxTmdbClient` with the placeholder key — but `dependency_overrides` replaces `get_tmdb_client` entirely, so routes never touch that client.
- `Generator[None, None]` is the correct mypy return type for a `yield` fixture. Import from `collections.abc`, not `typing`, under Python 3.12.

### `server/tests/api/test_movies.py`

```python
from fastapi.testclient import TestClient


def test_movie_search_returns_results(client: TestClient) -> None:
    response = client.get("/movies/search", params={"query": "fight"})
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["id"] == 550
    assert results[0]["title"] == "Fight Club"


def test_movie_search_response_is_camel_case(client: TestClient) -> None:
    response = client.get("/movies/search", params={"query": "fight"})
    result = response.json()[0]
    assert "releaseYear" in result
    assert "posterPath" in result
    assert "release_year" not in result
    assert "poster_path" not in result


def test_movie_search_missing_query_returns_422(client: TestClient) -> None:
    response = client.get("/movies/search")
    assert response.status_code == 422


def test_movie_credits_returns_cast_ids(client: TestClient) -> None:
    response = client.get("/movies/550/credits")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 550
    assert data["castIds"] == [819, 287]


def test_movie_credits_invalid_id_returns_422(client: TestClient) -> None:
    response = client.get("/movies/abc/credits")
    assert response.status_code == 422
```

### `server/tests/api/test_people.py`

```python
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
```

---

## Endpoint → code mapping

| Endpoint                    | Route function      | TmdbClient method   | Response model             |
| --------------------------- | ------------------- | ------------------- | -------------------------- |
| `GET /movies/search?query=` | `search_movies`     | `search_movies`     | `list[MovieSearchResult]`  |
| `GET /movies/{id}/credits`  | `get_movie_credits` | `get_movie_credits` | `MovieCreditsResult`       |
| `GET /people/search?query=` | `search_people`     | `search_people`     | `list[PersonSearchResult]` |

## Test case → test function mapping

| TC   | Scenario                              | Test function                                  |
| ---- | ------------------------------------- | ---------------------------------------------- |
| M-01 | Movie search returns results          | `test_movie_search_returns_results`            |
| M-02 | Movie search response uses camelCase  | `test_movie_search_response_is_camel_case`     |
| M-03 | Movie search missing query → 422      | `test_movie_search_missing_query_returns_422`  |
| M-04 | Movie credits returns cast IDs        | `test_movie_credits_returns_cast_ids`          |
| M-05 | Movie credits non-integer ID → 422    | `test_movie_credits_invalid_id_returns_422`    |
| P-01 | People search returns results         | `test_people_search_returns_results`           |
| P-02 | People search response uses camelCase | `test_people_search_response_is_camel_case`    |
| P-03 | People search missing query → 422     | `test_people_search_missing_query_returns_422` |

---

## Verification

Run from `server/`:

```bash
uv run ruff check .        # lint + import order
uv run mypy app            # strict type check
uv run pytest              # expect 21 passed (8 new + 12 engine + 1 health)
```

Expected pytest output:

```
collected 21 items
tests/api/test_movies.py .....
tests/api/test_people.py ...
tests/engine/test_engine.py ............
tests/test_health.py .
21 passed in 0.XXs
```

The full suite must stay green — the engine tests are the regression check that Phase 2 does not disturb Phase 1.

---

## Commit sequence

Two commits, each leaving the tree green:

1. `feat: add TMDB proxy models, HTTP client, and DI dependency` — `models/tmdb.py`, `tmdb_client.py`, `deps.py`, update `models/__init__.py`, `httpx` in `pyproject.toml`
2. `feat: add movie and people search endpoints with tests` — `api/movies.py`, `api/people.py`, update `api/__init__.py`, update `main.py`, `tests/conftest.py`, `tests/api/`

The first commit has no routes — `mypy app` and `ruff` pass because none of the new code is imported yet. The second commit wires everything together and turns the tests green.

---

## Risk flags

- **`httpx2` in production deps.** `httpx2` is currently a dev-only dependency. The TMDB client uses it at runtime — move it to `[project].dependencies` (or add it there alongside the dev entry). `TestClient` also uses it, so keeping it in dev deps is correct too; it just needs to be in both.
- **TMDB key at test startup.** Without `tests/conftest.py` setting `TMDB_API_KEY`, every test fails at lifespan startup with `KeyError`. The conftest fix is essential and must be committed in the same PR as the routes.
- **camelCase serialization correctness.** FastAPI infers the response model from the return type annotation and serializes Pydantic models by alias by default in FastAPI 0.137.x + Pydantic v2. The `test_*_response_is_camel_case` tests catch any misconfiguration. If those tests fail, check `model_config` settings and whether `alias_generator` is being applied correctly.
- **`release_year` null safety.** TMDB returns `release_date` as a string (`"YYYY-MM-DD"`), empty string (`""`), or absent/null. `(m.get("release_date") or "")[:4] or None` handles all three — the `or ""` converts `None` before slicing; the trailing `or None` converts an empty slice back to `None`. The simpler `m.get("release_date", "")[:4] or None` misses the `release_date: null` JSON case. Use the two-`or` form.
- **Page 1 only (D9).** If Phase 4's search UX needs more than ~20 results, this becomes visible. The missing `page` parameter should be noted in an OpenAPI `description` on both search routes; that makes the gap visible in the auto-generated docs without requiring a code change.
- **mypy and `Depends`.** Under `mypy --strict`, `Depends(get_tmdb_client)` may be typed as `Any` depending on FastAPI's stubs version. The explicit annotation `tmdb: TmdbClient = Depends(get_tmdb_client)` overrides any inference; mypy will trust the annotation and check route body usage against `TmdbClient`. If mypy still complains, add `# type: ignore[assignment]` with a comment explaining the gap — do not weaken the whole-file strictness.
- **Protocol drift.** mypy verifies `FakeTmdbClient` satisfies `TmdbClient` only at annotated usages. If a new method is added to the Protocol and `FakeTmdbClient` is not updated, mypy catches it only where `FakeTmdbClient` is assigned to a `TmdbClient`-typed variable. The `client` fixture in `conftest.py` does not annotate the override lambda's return type — consider adding a `_: TmdbClient = FakeTmdbClient()` assertion in `conftest.py` to keep mypy honest as the Protocol grows.
- **TMDB rate limits in CI.** Phase 2's tests use `FakeTmdbClient` — no real TMDB calls. But if someone adds a live integration test later (e.g., a `pytest -m integration` suite), it will need a real API key in CI secrets and should be excluded from the default `pytest` run. Defer that concern to when it's needed.
