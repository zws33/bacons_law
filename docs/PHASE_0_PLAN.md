# Phase 0 Implementation Plan — Foundation

Source of scope: [PYTHON_TS_REWRITE_PLAN.md](PYTHON_TS_REWRITE_PLAN.md#phase-0-foundation)

**Done when:** empty-but-wired apps build, lint, and test green in CI.

---

## Step 1 — Remove Kotlin artifacts

Delete from `fullstack-py-ts-rewrite` (they remain intact on `main`):

| Path                                                                            | Reason                                               |
| ------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `app/`, `backend/`, `core/`                                                     | Kotlin modules                                       |
| `build/`, `build.gradle.kts`, `buildscripts/`                                   | Gradle build                                         |
| `gradle/`, `gradle.properties`, `gradlew`, `gradlew.bat`, `settings.gradle.kts` | Gradle wrapper + config                              |
| `Dockerfile`                                                                    | Ktor-specific; FastAPI gets its own in Phase 5       |
| `scripts/deploy.sh`                                                             | Cloud Run deploy — replaced by Fly.io workflow later |

Keep: `docs/`, `CLAUDE.md`, `AGENTS.md`, `README.md`, `ROADMAP.md`, `GEMINI.md`.

Note: `local.properties` contains the TMDB API key and must not be committed. If it is currently tracked, remove it here. If untracked, no action needed.

Commit: `chore: remove kotlin modules and gradle from py-ts branch`

---

## Step 2 — `server/` FastAPI skeleton

### Directory structure

```
server/
├── pyproject.toml          # uv project; ruff + mypy + pytest config inline
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI app, GET /health → {"status": "ok"}
│   ├── engine/             # empty __init__.py (Phase 1 target)
│   ├── api/                # empty __init__.py (Phase 2 target)
│   ├── ws/                 # empty __init__.py (Phase 3 target)
│   ├── store/              # empty __init__.py (Phase 3 target)
│   └── models/             # empty __init__.py (Phase 2+ target)
└── tests/
    ├── __init__.py
    └── test_health.py      # httpx TestClient → GET /health → 200 {"status": "ok"}
```

### `pyproject.toml` shape

```toml
[project]
name = "bacons-law-server"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi",
  "uvicorn[standard]",
]

[tool.uv]
dev-dependencies = [
  "pytest",
  "pytest-asyncio",
  "httpx",
  "ruff",
  "mypy",
]

[tool.ruff]
line-length = 100
select = ["E", "F", "I"]   # pycodestyle errors, pyflakes, isort

[tool.mypy]
strict = true
python_version = "3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

### Verification (local)

```bash
cd server
uv sync
uv run ruff check .
uv run mypy app
uv run pytest
```

Commit: `feat: initialize fastapi server skeleton with health endpoint`

---

## Step 3 — pnpm workspace root + `web/`

### Workspace root

`pnpm-workspace.yaml` at the repo root:

```yaml
packages:
  - "web"
  - "packages/*"
```

### `web/`

Scaffold: `pnpm create vite web/ --template react-ts`

Then configure Tailwind CSS (v4, Vite plugin — not PostCSS):

```bash
cd web
pnpm add -D tailwindcss @tailwindcss/vite
```

`vite.config.ts` — add `tailwindcss()` to the Vite plugins array.

`src/index.css` — replace contents with `@import "tailwindcss";`

`tsconfig.json` — ensure `"strict": true`.

Add Vitest + React Testing Library:

```bash
pnpm add -D vitest @vitest/ui jsdom @testing-library/react @testing-library/jest-dom
```

`vite.config.ts` — add vitest test config block (`environment: "jsdom"`).

One placeholder test at `src/App.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import App from "./App";

it("renders without crashing", () => {
  render(<App />);
  expect(document.body).toBeTruthy();
});
```

Replace the default Vite `<App />` template content with a minimal Tailwind-styled element to prove Tailwind is wired (e.g. a `<h1>` with a Tailwind class).

### Verification (local)

```bash
cd web
pnpm tsc --noEmit
pnpm lint
pnpm test
```

Commit: `feat: initialize pnpm workspace with web and game-client packages`

---

## Step 4 — `packages/game-client/`

### Structure

```
packages/game-client/
├── package.json
├── tsconfig.json
└── src/
    └── index.ts    # export {} — empty barrel, placeholder for Phase 3+
```

### `package.json`

```json
{
  "name": "@bacons-law/game-client",
  "version": "0.0.1",
  "type": "module",
  "main": "./src/index.ts",
  "scripts": {
    "typecheck": "tsc --noEmit"
  }
}
```

### `tsconfig.json`

```json
{
  "compilerOptions": {
    "strict": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "noEmit": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

Wire into `web/` by adding to `web/package.json`:

```json
"dependencies": {
  "@bacons-law/game-client": "workspace:*"
}
```

Then `pnpm install` from the repo root to link the workspace.

Included in the same commit as Step 3.

---

## Step 5 — GitHub Actions CI

### `.github/workflows/ci.yml`

```yaml
name: CI

on:
  pull_request:
    branches:
      - fullstack-py-ts-rewrite

jobs:
  server-ci:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: server
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.12"
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run mypy app
      - run: uv run pytest

  web-ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 10
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: pnpm
      - run: pnpm install --frozen-lockfile
      - run: pnpm --filter web tsc --noEmit
      - run: pnpm --filter web lint
      - run: pnpm --filter web test --run
```

Commit: `ci: add github actions workflow for server and web`

---

## Commit sequence

1. `chore: remove kotlin modules and gradle from py-ts branch`
2. `feat: initialize fastapi server skeleton with health endpoint`
3. `feat: initialize pnpm workspace with web and game-client packages`
4. `ci: add github actions workflow for server and web`

---

## Risk flags

- **Tailwind v4** uses the Vite plugin (`@tailwindcss/vite`), not the PostCSS approach documented in most tutorials. Verify against current Tailwind docs when implementing.
- **`mypy --strict` on empty modules** will pass trivially in Phase 0. Real type discipline comes in Phase 1 when engine types are introduced — that's expected.
- **`uv sync --frozen` in CI** requires a committed `uv.lock`. Running `uv sync` locally before committing generates it. Don't skip this.
- **pnpm lockfile** — `pnpm install` from the repo root must be run after wiring `game-client` as a workspace dep, and the resulting `pnpm-lock.yaml` must be committed before CI runs `--frozen-lockfile`.
