"""FastAPI application: REST endpoints + WebSocket room chat with dice rolls."""

import asyncio
import os
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from . import database as db
from .dice import DiceError, roll

NAME_RE = re.compile(r"^[\w\- ]{2,24}$", re.UNICODE)
MAX_CHAT_LENGTH = 500

# WebSocket close codes (4000-4999 are reserved for applications).
CLOSE_BAD_REQUEST = 4400
CLOSE_NOT_FOUND = 4404
CLOSE_CONFLICT = 4409


def validate_name(value: str, field: str) -> str:
    value = (value or "").strip()
    if not NAME_RE.match(value):
        raise ValueError(f"{field} must be 2-24 characters: letters, numbers, spaces, '-' or '_'")
    return value


class LoginRequest(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        return validate_name(v, "username")


class RollRequest(BaseModel):
    expression: str


@dataclass
class Client:
    websocket: WebSocket
    player: dict


class RoomManager:
    """Keeps track of live WebSocket connections grouped by room id."""

    def __init__(self) -> None:
        self.rooms: dict[int, list[Client]] = {}

    def clients(self, room_id: int) -> list[Client]:
        return list(self.rooms.get(room_id, []))

    def is_connected(self, room_id: int, username: str) -> bool:
        return any(
            c.player["username"].lower() == username.lower() for c in self.rooms.get(room_id, [])
        )

    def add(self, room_id: int, client: Client) -> None:
        self.rooms.setdefault(room_id, []).append(client)

    def remove(self, room_id: int, client: Client) -> None:
        clients = self.rooms.get(room_id, [])
        if client in clients:
            clients.remove(client)
        if not clients:
            self.rooms.pop(room_id, None)

    async def broadcast(self, room_id: int, payload: dict) -> None:
        for client in self.clients(room_id):
            try:
                await client.websocket.send_json(payload)
            except Exception:
                # The disconnect handler of that socket will clean it up.
                pass


manager = RoomManager()
# Strong references to fire-and-forget tasks so they are not garbage collected.
background_tasks: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Fiasco", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- REST ----------

@app.post("/api/login")
def login(body: LoginRequest) -> dict:
    return db.upsert_player(body.username)


@app.get("/api/rooms")
def get_rooms() -> list[dict]:
    return db.list_rooms()


@app.get("/api/rooms/{name}/players")
def get_room_players(name: str) -> list[dict]:
    room = db.get_room(name)
    if not room:
        raise HTTPException(404, "Room not found")
    return db.list_members(room["id"])


@app.get("/api/players/{username}/rolls")
def get_player_rolls(username: str) -> list[dict]:
    return db.player_rolls(username)


@app.post("/api/roll")
def roll_preview(body: RollRequest) -> dict:
    """Stateless roll, useful for testing expressions without a room."""
    try:
        return roll(body.expression).to_dict()
    except DiceError as exc:
        raise HTTPException(400, str(exc))


# ---------- WebSocket ----------

async def reject(websocket: WebSocket, code: int, reason: str) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "error", "message": reason})
    await websocket.close(code=code, reason=reason)


@app.websocket("/ws")
async def room_socket(websocket: WebSocket, room: str = "", username: str = "", mode: str = "join"):
    try:
        room_name = validate_name(room, "room")
        username = validate_name(username, "username")
    except ValueError as exc:
        await reject(websocket, CLOSE_BAD_REQUEST, str(exc))
        return
    if mode not in ("join", "create"):
        await reject(websocket, CLOSE_BAD_REQUEST, "mode must be 'join' or 'create'")
        return

    player = db.upsert_player(username)

    # Checks and state changes below run without any await in between, so on the
    # single-threaded event loop they are atomic: no other join/leave can interleave.
    existing = db.get_room(room_name)
    error = None
    if mode == "create" and existing:
        error = (CLOSE_CONFLICT, f"Room '{room_name}' already exists")
    elif mode == "join" and not existing:
        error = (CLOSE_NOT_FOUND, f"Room '{room_name}' does not exist")
    elif existing and manager.is_connected(existing["id"], username):
        error = (CLOSE_CONFLICT, f"'{username}' is already in this room")
    if error:
        await reject(websocket, *error)
        return

    current_room = existing or db.create_room(room_name, player["id"])
    room_id = current_room["id"]
    client = Client(websocket=websocket, player=player)
    manager.add(room_id, client)
    db.add_member(room_id, player["id"])

    try:
        await websocket.accept()
        await websocket.send_json({
            "type": "welcome",
            "room": current_room["name"],
            "username": player["username"],
            "history": db.room_history(room_id),
            "players": db.list_members(room_id),
        })
        await announce(room_id, f"{player['username']} joined the room")

        while True:
            data = await websocket.receive_json()
            await handle_message(current_room, client, data)
    except WebSocketDisconnect:
        pass
    except Exception:
        # Malformed frames or unexpected errors: drop the connection cleanly.
        pass
    finally:
        leave(room_id, client)


async def handle_message(room: dict, client: Client, data: dict) -> None:
    player = client.player
    kind = data.get("type") if isinstance(data, dict) else None

    if kind == "chat":
        text = str(data.get("text", "")).strip()[:MAX_CHAT_LENGTH]
        if not text:
            return
        msg = db.save_message(room["id"], player["id"], "chat", text)
        await manager.broadcast(room["id"], {
            "type": "chat",
            "username": player["username"],
            "text": text,
            "created_at": msg["created_at"],
        })

    elif kind == "roll":
        try:
            result = roll(str(data.get("expression", "")))
        except DiceError as exc:
            await client.websocket.send_json({"type": "error", "message": str(exc)})
            return
        detail = result.to_dict()
        saved = db.save_roll(room, player["id"], result.expression, detail, result.total)
        await manager.broadcast(room["id"], {
            "type": "roll",
            "username": player["username"],
            "result": detail,
            "created_at": saved["created_at"],
        })

    else:
        await client.websocket.send_json({"type": "error", "message": "Unknown message type"})


async def announce(room_id: int, text: str, msg: dict | None = None) -> None:
    msg = msg or db.save_message(room_id, None, "system", text)
    await manager.broadcast(room_id, {"type": "system", "text": text, "created_at": msg["created_at"]})
    await manager.broadcast(room_id, {"type": "players", "players": db.list_members(room_id)})


def leave(room_id: int, client: Client) -> None:
    # State cleanup is synchronous so it completes even if the task is being cancelled.
    manager.remove(room_id, client)
    remaining = db.remove_member(room_id, client.player["id"])
    if remaining == 0:
        # Last player left: the room (and its chat) is deleted; rolls stay as history.
        db.delete_room(room_id)
        return
    text = f"{client.player['username']} left the room"
    msg = db.save_message(room_id, None, "system", text)
    # Run detached: the leaving socket's task may be getting cancelled right now.
    task = asyncio.create_task(announce(room_id, text, msg))
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


# Serve the compiled Angular app when it exists (production mode).
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist", "frontend", "browser")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
