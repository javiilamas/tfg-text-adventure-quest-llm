
from pathlib import Path
from src.engine.loader import load_json, validate_world, build_world, bootstrap_state
from src.engine.engine import look, take, use, move

def test_full_flow():
    wd = load_json(Path("worlds/v1/demo_world.json"))
    validate_world(wd, Path("worlds/world_schema.json"))
    w = build_world(wd)
    s = bootstrap_state(w)
    assert look(w, s)["ok"]
    assert take(w, s, "key")["ok"]
    assert use(w, s, "key", "door")["ok"]
    res = move(w, s, "north")
    assert res["ok"]
    assert res["state"]["room"] == "library"
