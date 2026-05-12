
from pathlib import Path
from src.engine.loader import load_json, validate_world, build_world, bootstrap_state
from src.engine.engine import look, move, take, drop, use, state_view

def setup_world():
    wd = load_json(Path("worlds/v1/demo_world.json"))
    validate_world(wd, Path("worlds/world_schema.json"))
    w = build_world(wd)
    s = bootstrap_state(w)
    return w, s

def test_look_and_state():
    w, s = setup_world()
    r = look(w, s)
    assert r["ok"] and "Salidas" in r["narration"]
    r2 = state_view(w, s)
    assert r2["ok"] and "state" in r2

def test_take_and_drop():
    w, s = setup_world()
    # Hall tiene key
    r = take(w, s, "key")
    assert r["ok"]
    assert "key" in r["state"]["inventory"]
    r = drop(w, s, "key")
    assert r["ok"]
    assert "key" not in r["state"]["inventory"]

def test_use_and_move_rules():
    w, s = setup_world()
    # Coger llave
    assert take(w, s, "key")["ok"]
    # Abrir puerta
    r = use(w, s, "key", "door")
    assert r["ok"]
    assert r["state"]["flags"]["door_open"] is True
    # Mover al norte
    r = move(w, s, "north")
    assert r["ok"]
    assert r["state"]["room"] == "library"

def test_invalid_move():
    w, s = setup_world()
    r = move(w, s, "north")  # puerta cerrada
    assert not r["ok"]
    assert r["error"]["code"] == "RULE_BLOCKED"
