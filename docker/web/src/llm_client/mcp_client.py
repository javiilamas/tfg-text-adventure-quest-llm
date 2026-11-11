"""Router de tools.

Traduce cada tool del LLM a una operacion del SessionManager, que a su vez la
delega al motor activo (Quest o Frotz). Se mantiene el nombre `call_tool` y la
firma compatible con la version anterior (con un session_id opcional anadido
para soportar multiples usuarios/partidas).

IMPORTANTE: ninguna tool ejecuta comandos del sistema. send_game_command solo
escribe texto en la entrada del motor del juego.
"""
from __future__ import annotations

from .catalog import list_games as catalog_list_games
from .sessions import MANAGER


def call_tool(name: str, args: dict | None = None, session_id: str = "web") -> dict:
    args = args or {}

    if name == "list_games":
        return {"games": catalog_list_games()}

    if name == "start_game":
        game_id = args.get("game_id")
        if not game_id:
            return {"ok": False, "error": "MISSING_game_id", "games": catalog_list_games()}
        return MANAGER.start_game(session_id, game_id).to_dict()

    if name == "current_game":
        cur = MANAGER.current(session_id)
        return {"active": cur is not None, **(cur or {})}

    if name == "close_game":
        MANAGER.close(session_id)
        return {"ok": True, "closed": True}

    if name == "send_game_command":
        command = (args.get("command") or "").strip()
        if not command:
            return {"ok": False, "error": "MISSING_command"}
        return MANAGER.send_command(session_id, command).to_dict()

    if name == "look":
        return MANAGER.look(session_id).to_dict()

    if name == "move":
        direction = args.get("direction", "north")
        return MANAGER.move(session_id, direction).to_dict()

    if name == "new_game":
        cur = MANAGER.current(session_id)
        game_id = (cur or {}).get("game_id", "quest_tutorial")
        return MANAGER.start_game(session_id, game_id).to_dict()

    return {"ok": False, "error": f"UNKNOWN_TOOL: {name}"}
