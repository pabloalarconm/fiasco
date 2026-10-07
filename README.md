# Fiasco

Real-time dice roller for tabletop games (D&D, Warhammer 40K and friends).

- **Backend**: Python + FastAPI, WebSockets, SQLite (`backend/`)
- **Frontend**: Angular (`frontend/`)

## Features

- Username-only login (no password).
- Create a room or join an existing one (lobby lists open rooms and player counts).
- Live player list for everyone in the room.
- Room chat over WebSocket; every roll is broadcast to the whole room.
- Dice picker per game system:
  - **D&D**: d2, d4, d6, d8, d10, d12, d20, d100 and a modifier (advantage/disadvantage
    via custom expressions `2d20kh1` / `2d20kl1`).
  - **Warhammer 40K**: d3 and d6, either summed (damage, charges) or as an "X+" test
    that counts successes (hits, wounds, saves).
- Free-form expressions like `4d6kh3+2`, `1d20+1d4-1` or `10d6>=3`, with in-app syntax help.
- SQLite stores players, rooms, chat and rolls. When the last player leaves,
  the room and its chat are deleted; rolls are kept as history.

## Run (development)

```bash
# Backend (port 8000)
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload

# Frontend (port 4200, proxies /api and /ws to :8000)
cd frontend
npm install
npx ng serve
```

Open http://localhost:4200 in several browser tabs with different usernames.

## Run (single server)

```bash
cd frontend && npx ng build
cd ../backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0
```

The backend serves the compiled Angular app at http://localhost:8000.

## Run (Docker)

```bash
docker compose up -d --build
```

A multi-stage build compiles the Angular app and serves it together with the API and
WebSocket at http://localhost:8000. The SQLite database lives in the `fiasco-data` volume
(`/data/dice.db`), so roll history survives restarts. Uvicorn runs a single worker on
purpose: live rooms are tracked in memory.

## Tests

```bash
cd backend && .venv/bin/python -m pytest
cd frontend && npx ng test --watch=false
```

## Dice expression syntax

| Expression  | Meaning                                  |
|-------------|------------------------------------------|
| `d20`       | One d20                                  |
| `3d6+2`     | Three d6 plus 2                          |
| `2d20kh1`   | Advantage (keep highest of two d20)      |
| `2d20kl1`   | Disadvantage (keep lowest of two d20)    |
| `4d6kh3`    | Ability score roll                       |
| `10d6>=3`   | Count dice showing 3 or more (Warhammer "3+" test) |

## WebSocket protocol

Connect to `/ws?room=<name>&username=<name>&mode=create|join`.

Client → server:
- `{"type": "chat", "text": "..."}`
- `{"type": "roll", "expression": "1d20+5"}`

Server → client: `welcome` (history + players), `players`, `chat`, `system`, `roll`, `error`.
Close codes: `4400` bad request, `4404` room not found, `4409` room already exists / username already in room.

## REST endpoints

- `POST /api/login` `{username}`
- `GET /api/rooms`
- `GET /api/rooms/{name}/players`
- `GET /api/players/{username}/rolls`
- `POST /api/roll` `{expression}` (stateless roll)
