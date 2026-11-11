"""QuestEngine: adapta el Bridge (FastAPI + Playwright) actual a GameEngine.

NO reimplementa nada de Quest: reutiliza tal cual los endpoints del Bridge que
ya funcionan (/session/new, /session/command, /session/close). Asi la
integracion Quest existente se conserva intacta y pasa a ser "un motor mas".
"""
from __future__ import annotations
import os
import requests
from .base import GameEngine, EngineResult


class QuestEngine(GameEngine):
    name = "quest"

    def __init__(self, bridge_base: str | None = None, timeout: float = 120.0):
        self.bridge = (bridge_base or os.getenv("BRIDGE_BASE", "http://127.0.0.1:8787")).rstrip("/")
        self.timeout = timeout

    def start_game(self, session_id: str, game) -> EngineResult:
        try:
            r = requests.post(
                f"{self.bridge}/session/new",
                json={"sessionId": session_id, "questFilePath": game.path},
                timeout=self.timeout,
            )
            data = _safe_json(r)
        except Exception as e:  # red/bridge caido
            return EngineResult(ok=False, error=f"BRIDGE_UNREACHABLE: {e}")
        ok = bool(data.get("ok", r.ok))
        return EngineResult(ok=ok, output=str(data.get("message", "")), meta=data,
                            error=None if ok else str(data))

    def send_command(self, session_id: str, command: str) -> EngineResult:
        try:
            r = requests.post(
                f"{self.bridge}/session/command",
                json={"sessionId": session_id, "text": command},
                timeout=self.timeout,
            )
            data = _safe_json(r)
        except Exception as e:
            return EngineResult(ok=False, error=f"BRIDGE_UNREACHABLE: {e}")
        if r.status_code == 404:
            return EngineResult(ok=False, error="SESSION_NOT_FOUND")
        ok = bool(data.get("ok", r.ok))
        meta = {k: v for k, v in data.items() if k != "output"}
        return EngineResult(ok=ok, output=str(data.get("output", "")),
                            changed=bool(data.get("changed", True)), meta=meta)

    def move(self, session_id: str, direction: str) -> EngineResult:
        # Dialecto Quest: "go east"
        return self.send_command(session_id, f"go {direction}")

    def close_game(self, session_id: str) -> None:
        try:
            # El endpoint del Bridge declara sessionId como query param.
            requests.post(f"{self.bridge}/session/close",
                          params={"sessionId": session_id}, timeout=30)
        except Exception:
            pass


def _safe_json(r) -> dict:
    try:
        data = r.json()
        return data if isinstance(data, dict) else {"raw": data}
    except Exception:
        return {"raw": r.text}
