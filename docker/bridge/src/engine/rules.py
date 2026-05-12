
from typing import Any, Dict
from .models import World, GameState

def cond_ok(cond: Dict[str, Any], world: World, state: GameState) -> bool:
    if not cond:
        return True
    if "room" in cond and state.room != cond["room"]:
        return False
    if "hasItem" in cond and cond["hasItem"] not in state.inventory:
        return False
    if "flagEquals" in cond:
        key, val = cond["flagEquals"]
        if state.flags.get(key) != val:
            return False
    return True

def apply_then(then: Dict[str, Any], world: World, state: GameState) -> str:
    narration_parts = []
    if "setFlag" in then:
        k, v = then["setFlag"]
        state.flags[k] = v
    if "moveTo" in then:
        dest = then["moveTo"]
        state.room = dest
    if "takeFromRoom" in then:
        item = then["takeFromRoom"]
        if item in state.room_items[state.room]:
            state.room_items[state.room].remove(item)
            state.inventory.append(item)
    if "give" in then:
        item = then["give"]
        if item not in state.inventory:
            state.inventory.append(item)
    if "removeFromInventory" in then:
        item = then["removeFromInventory"]
        if item in state.inventory:
            state.inventory.remove(item)
    if "narration" in then:
        narration_parts.append(then["narration"])
    return " ".join(narration_parts)
