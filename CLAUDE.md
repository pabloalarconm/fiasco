# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Real-time multiplayer dice roller for tabletop RPGs: a FastAPI + SQLite backend (`backend/`) and an Angular frontend (`frontend/`), connected through a per-room WebSocket.

## Commands

Backend (run from `backend/`, venv at `backend/.venv`):

```bash
.venv/bin/uvicorn app.main:app --port 8000          # run API + WebSocket
.venv/bin/python -m pytest                          # all tests
.venv/bin/python -m pytest tests/test_dice.py::test_keep_highest_and_lowest   # single test
```

Frontend (run from `frontend/`; Node comes from nvm, so run `source ~/.nvm/nvm.sh` first in a fresh shell):

```bash
npx ng serve --watch=false        # dev server :4200, proxies /api and /ws to :8000 (proxy.conf.json)
npx ng build                      # output to dist/frontend/browser
npx ng test --watch=false         # Vitest unit tests
npx ng test --watch=false --include src/app/roll-card/roll-card.spec.ts   # single spec file
```

On this machine the inotify watcher limit is too low: `ng serve` crashes with `ENOSPC` unless you pass `--watch=false`, and `uvicorn --reload` silently never reloads. After you change code, restart the servers by hand.

When `frontend/dist/frontend/browser` exists, the backend also serves the built Angular app at `/`, so after `ng build` you only need uvicorn.

## Architecture

### Room lifecycle: the WebSocket is the source of truth

Rooms are **only** created and joined through `GET /ws?room=&username=&mode=create|join` in `backend/app/main.py`. There is no REST endpoint that creates a room. This design means a room exists only while at least one socket is connected:

- On connect, the server checks the request, creates the room if needed, and registers the client in both the in-memory `RoomManager` (live sockets, keyed by room id) and the `room_members` table.
- On disconnect, `leave()` removes the member. If no members remain, it deletes the room, and the cascade deletes its chat `messages`.
- `init_db()` deletes every room at startup, because no socket survives a restart.

**Concurrency invariant:** the join checks and state changes, and the cleanup in `leave()`, are deliberately written as synchronous code with no `await` in between. That makes them atomic on the single-threaded event loop, so no lock is needed. `leave()` is a plain `def` so it still completes when the handler task is cancelled. Starlette's TestClient cancels the handler on close, and server shutdown can too. The "X left" broadcast therefore runs as a detached task (`background_tasks`). If you add an `await` inside these sections, you break this invariant.

Rejections accept the socket, send `{"type":"error"}`, then close with an app code: `4400` bad input, `4404` room missing, `4409` room already exists or username already connected in that room.

### Persistence (`backend/app/database.py`)

This module uses plain `sqlite3`, one connection per call via the `connect()` context manager, with foreign keys turned on. Set `DICE_DB_PATH` to choose the database file; it defaults to `backend/dice.db`, and tests point it at a tmp path through monkeypatch in `conftest.py`. Names are unique `COLLATE NOCASE`.

`rolls` uses `ON DELETE SET NULL` and stores `room_name` as a copy, so roll history outlives deleted rooms. `messages` cascades with its room. Timestamps are ISO strings with milliseconds, and `room_history()` relies on them to interleave chat and rolls in order.

### Dice engine (`backend/app/dice.py`)

This module parses expressions like `2d20kh1+3d6-1`: `+`/`-` terms, `NdM`, optional `khK`/`klK` (keep highest/lowest K), optional `>=T` (count the kept dice showing T or more; the term's subtotal is the number of successes), and flat numbers. It uses `secrets.SystemRandom`. Each term reports `sides` (`null` for flat numbers), `rolls` (every die), `kept` and `target` (`null` unless `>=T`; for success terms `kept` holds the successes). The frontend depends on these fields:

- `sides` drives the green (max face) / red (face 1) highlighting in `roll-card`.
- `rolls` vs `kept` drives the struck-through dropped dice.

If you change the shape of the roll result, also update `RollTerm` in `frontend/src/app/core/models.ts`.

### Frontend (`frontend/src/app`)

This is an Angular 22 app made of standalone components with signals and zone.js change detection. It has no router: `App` shows login, lobby or room through a `computed` view based on `SessionService.username()` and `RoomSocketService.state()`.

- `core/session.service.ts`: login with only a username, stored in localStorage; REST calls.
- `core/room-socket.service.ts`: owns the single WebSocket and exposes `players`, `feed`, `error`, `state` as signals. The room view is shown only after the server's `welcome` message arrives.
- `dice-panel/expression.ts`: `GAME_SYSTEMS` lists the game systems (D&D, Warhammer 40K) and the dice each one offers; `buildExpression()` turns the dice picker state into a backend expression. In Warhammer, an "X+" test turns the d6 pool into `Nd6>=X` and ignores the other dice and the modifier.

The WebSocket message types are described in `README.md` and typed in `models.ts` (`ServerMessage`, `FeedEntry`).

## Conventions

- Write code, identifiers and UI text in English. The user talks to you in Spanish.
- Keep backend error messages in English; the frontend shows them unchanged.
