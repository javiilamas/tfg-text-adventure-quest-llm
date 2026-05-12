
from pathlib import Path
from src.engine.loader import load_json, validate_world, build_world, bootstrap_state

def test_world_load_and_validate():
    world_path = Path("worlds/v1/demo_world.json")
    schema_path = Path("worlds/world_schema.json")
    wd = load_json(world_path)
    validate_world(wd, schema_path)
    w = build_world(wd)
    s = bootstrap_state(w)
    assert s.room == wd["start"]["room"]
    assert set(s.inventory) == set(wd["start"]["inventory"])
    # Rooms copied to mutable state
    assert set(s.room_items.keys()) == set(w.rooms.keys())
