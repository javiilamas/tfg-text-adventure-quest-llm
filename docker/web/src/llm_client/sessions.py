"""Gestion de sesiones multi-motor / multi-juego.

Sustituye al `sessionId="demo"` fijo. Cada sesion sabe que juego y que motor
tiene activos; el estado interno de la partida lo guarda CADA motor (el Bridge
para Quest, el proceso dfrotz para Frotz), nunca una variable global.
"""
from __future__ import annotations
import threading

from .catalog import get_game
from .engines import QuestEngine, FrotzEngine, EngineResult


class SessionManager:
    def __init__(self):
        self._engines = {
            "quest": QuestEngine(),
            "frotz": FrotzEngine(),
        }
        self._sessions: dict[str, dict] = {}
        self._lock = threading.Lock()

    # --- consulta ---
    def current(self, session_id: str) -> dict | None:
        with self._lock:
            s = self._sessions.get(session_id)
            return dict(s) if s else None

    # --- ciclo de vida ---
    def start_game(self, session_id: str, game_id: str) -> EngineResult:
        game = get_game(game_id)
        if game is None:
            return EngineResult(ok=False, error=f"UNKNOWN_GAME: {game_id}")
        engine = self._engines.get(game.engine)
        if engine is None:
            return EngineResult(ok=False, error=f"UNKNOWN_ENGINE: {game.engine}")
        self.close(session_id)  # cierra cualquier partida previa de esta sesion
        res = engine.start_game(session_id, game)
        if res.ok:
            with self._lock:
                self._sessions[session_id] = {
                    "game_id": game.id, "name": game.name, "engine": game.engine,
                }
        return res

    def send_command(self, session_id: str, command: str) -> EngineResult:
        engine, _ = self._active(session_id)
        if engine is None:
            return EngineResult(ok=False, error="NO_ACTIVE_GAME")
        return engine.send_command(session_id, command)

    def move(self, session_id: str, direction: str) -> EngineResult:
        engine, _ = self._active(session_id)
        if engine is None:
            return EngineResult(ok=False, error="NO_ACTIVE_GAME")
        return engine.move(session_id, direction)

    def look(self, session_id: str) -> EngineResult:
        engine, _ = self._active(session_id)
        if engine is None:
            return EngineResult(ok=False, error="NO_ACTIVE_GAME")
        return engine.get_state(session_id)

    def close(self, session_id: str) -> None:
        with self._lock:
            s = self._sessions.pop(session_id, None)
        if s:
            engine = self._engines.get(s["engine"])
            if engine:
                engine.close_game(session_id)

    # --- interno ---
    def _active(self, session_id: str):
        with self._lock:
            s = self._sessions.get(session_id)
        if not s:
            return None, None
        return self._engines.get(s["engine"]), s


# Instancia compartida por el proceso web.
MANAGER = SessionManager()
