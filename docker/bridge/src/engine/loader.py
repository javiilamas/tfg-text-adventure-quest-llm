
import json
from pathlib import Path
from jsonschema import validate, Draft202012Validator
from .models import World, Room, GameState

def load_json(path: Path | str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def validate_world(world_dict: dict, schema_path: Path | str) -> None:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(world_dict), key=lambda e: e.path)
    if errors:
        msgs = "\n".join(f"- {'/'.join(map(str,e.path))}: {e.message}" for e in errors)
        raise ValueError(f"World JSON violates schema:\n{msgs}")

def build_world(world_dict: dict) -> World:
    rooms = {k: Room(**v) for k, v in world_dict["rooms"].items()}
    return World(
        meta=world_dict["meta"],
        start=world_dict["start"],
        rooms=rooms,
        items=world_dict["items"],
        rules=world_dict["rules"]
    )

def bootstrap_state(world: World) -> GameState:
    start = world.start
    room_items = {name: list(room.items) for name, room in world.rooms.items()}
    return GameState(
        room=start["room"],
        inventory=list(start["inventory"]),
        flags=dict(start["flags"]),
        room_items=room_items
    )
