
from typing import Dict, Any, Optional
from .models import World, GameState
from .rules import cond_ok, apply_then

def result(ok: bool, state: GameState, narration: str = "", error: Dict[str, str] | None = None) -> Dict[str, Any]:
    payload = {
        "ok": ok,
        "state": {"room": state.room, "inventory": list(state.inventory), "flags": dict(state.flags)},
    }
    if ok:
        payload["narration"] = narration
    else:
        payload["error"] = error or {"code":"UNKNOWN","message":"Unknown error"}
    return payload

def look(world: World, state: GameState) -> Dict[str, Any]:
    room = world.rooms[state.room]
    exits = ", ".join(room.exits.keys()) or "ninguna"
    items = ", ".join(state.room_items[state.room]) or "ninguno"
    narration = f"{room.desc} Salidas: {exits}. Objetos: {items}."
    return result(True, state, narration)

def move(world: World, state: GameState, direction: str) -> Dict[str, Any]:
    room = world.rooms[state.room]

    # Buscar si hay reglas específicas para este movimiento
    matching_rules = [
        rule for rule in world.rules
        if rule["when"] == f"move({direction})"
    ]

    narration_parts = []

    if matching_rules:
        # Si hay reglas, SOLO esas reglas controlan el movimiento
        applied = False
        for rule in matching_rules:
            if cond_ok(rule.get("if", {}), world, state):
                narration_parts.append(apply_then(rule["then"], world, state))
                applied = True

        if applied:
            # La regla se cumplió → movimiento OK
            return result(True, state, " ".join(narration_parts))
        else:
            # Había una regla, pero no se cumplió → movimiento bloqueado
            return result(
                False,
                state,
                error={
                    "code": "RULE_BLOCKED",
                    "message": f"No puedes ir hacia {direction} ahora."
                }
            )

    # Si NO hay reglas, usar la salida por defecto del mapa
    if direction not in room.exits:
        return result(
            False,
            state,
            error={"code": "NO_EXIT", "message": "No hay salida en esa dirección."}
        )

    state.room = room.exits[direction]
    return result(True, state, f"Te mueves hacia {direction}.")


def take(world: World, state: GameState, item: str) -> Dict[str, Any]:
    if item not in world.items:
        return result(False, state, error={"code":"ITEM_UNKNOWN","message":"Ese objeto no existe."})
    if item not in state.room_items[state.room]:
        return result(False, state, error={"code":"ITEM_NOT_FOUND","message":"Aquí no está ese objeto."})
    if not world.items[item].get("portable", False):
        return result(False, state, error={"code":"NOT_PORTABLE","message":"No puedes llevar eso."})
    state.room_items[state.room].remove(item)
    state.inventory.append(item)
    return result(True, state, f"Coges {item}.")

def drop(world: World, state: GameState, item: str) -> Dict[str, Any]:
    if item not in state.inventory:
        return result(False, state, error={"code":"NOT_INVENTORY","message":"No llevas ese objeto."})
    state.inventory.remove(item)
    state.room_items[state.room].append(item)
    return result(True, state, f"Dejas {item} en el suelo.")

def use(world: World, state: GameState, item: str, target: Optional[str] = None) -> Dict[str, Any]:
    narration_parts = []
    matched = False
    when = f"use({item})" if target is None else f"use({item},{target})"
    for rule in world.rules:
        if rule["when"] != when:
            continue
        matched = True
        if cond_ok(rule.get("if", {}), world, state):
            narration_parts.append(apply_then(rule["then"], world, state))
    if matched and narration_parts:
        return result(True, state, " ".join(narration_parts))
    if matched and not narration_parts:
        return result(False, state, error={"code":"RULES_BLOCK","message":"No pasa nada al usar eso ahora."})
    return result(False, state, error={"code":"NO_RULE","message":"No ocurre nada al usar eso."})

def state_view(world: World, state: GameState) -> Dict[str, Any]:
    return result(True, state, narration="")
