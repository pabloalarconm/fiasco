import pytest
from starlette.websockets import WebSocketDisconnect


def ws_url(room, user, mode):
    return f"/ws?room={room}&username={user}&mode={mode}"


def test_login_creates_player(client):
    r = client.post("/api/login", json={"username": "Gandalf"})
    assert r.status_code == 200
    assert r.json()["username"] == "Gandalf"
    assert client.post("/api/login", json={"username": "x"}).status_code == 422


def test_join_missing_room_is_rejected(client):
    with client.websocket_connect(ws_url("Nope", "Frodo", "join")) as ws:
        assert ws.receive_json()["type"] == "error"
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4404


def test_full_room_lifecycle(client):
    with client.websocket_connect(ws_url("Moria", "Gandalf", "create")) as gandalf:
        welcome = gandalf.receive_json()
        assert welcome["type"] == "welcome"
        assert [p["username"] for p in welcome["players"]] == ["Gandalf"]
        assert gandalf.receive_json()["type"] == "system"
        assert gandalf.receive_json()["type"] == "players"

        # Creating the same room again fails
        with client.websocket_connect(ws_url("moria", "Pippin", "create")) as dup:
            assert dup.receive_json()["type"] == "error"

        with client.websocket_connect(ws_url("Moria", "Frodo", "join")) as frodo:
            welcome = frodo.receive_json()
            assert [p["username"] for p in welcome["players"]] == ["Gandalf", "Frodo"]
            frodo.receive_json(); frodo.receive_json()  # system + players
            gandalf.receive_json()
            players = gandalf.receive_json()
            assert [p["username"] for p in players["players"]] == ["Gandalf", "Frodo"]

            # Same username cannot join twice
            with client.websocket_connect(ws_url("Moria", "Frodo", "join")) as twin:
                assert twin.receive_json()["type"] == "error"

            assert client.get("/api/rooms").json()[0]["player_count"] == 2

            frodo.send_json({"type": "chat", "text": "Hello"})
            for ws in (gandalf, frodo):
                msg = ws.receive_json()
                assert msg == {**msg, "type": "chat", "username": "Frodo", "text": "Hello"}

            gandalf.send_json({"type": "roll", "expression": "2d20kh1+5"})
            for ws in (gandalf, frodo):
                msg = ws.receive_json()
                assert msg["type"] == "roll"
                assert 6 <= msg["result"]["total"] <= 25

            gandalf.send_json({"type": "roll", "expression": "bad"})
            assert gandalf.receive_json()["type"] == "error"

        # Frodo left: Gandalf is notified
        assert gandalf.receive_json()["text"] == "Frodo left the room"
        assert [p["username"] for p in gandalf.receive_json()["players"]] == ["Gandalf"]

        # A rejoining player receives the history
        with client.websocket_connect(ws_url("Moria", "Sam", "join")) as sam:
            history = sam.receive_json()["history"]
            assert any(h["type"] == "roll" for h in history)
            assert any(h["type"] == "chat" and h["text"] == "Hello" for h in history)

    # Everyone left: the room is deleted, rolls remain
    assert client.get("/api/rooms").json() == []
    rolls = client.get("/api/players/Gandalf/rolls").json()
    assert len(rolls) == 1 and rolls[0]["room_name"] == "Moria"
