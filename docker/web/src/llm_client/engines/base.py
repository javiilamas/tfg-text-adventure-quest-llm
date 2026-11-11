"""Abstraccion comun de motores de aventura.

Todos los motores (Quest, Frotz, ...) implementan la MISMA interfaz, de modo
que el resto de la aplicacion (Flask, cliente LLM, tools) no necesita saber con
que motor esta hablando. El motor es siempre la FUENTE DE VERDAD de la partida:
el LLM nunca inventa el resultado, solo decide que texto enviar.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class EngineResult:
    ok: bool
    output: str = ""          # texto real devuelto por el motor
    changed: bool = True      # si la salida cambio respecto al estado previo
    meta: Optional[dict] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


class GameEngine(ABC):
    """Contrato unico para cualquier motor de aventura."""

    name: str = "base"

    @abstractmethod
    def start_game(self, session_id: str, game) -> EngineResult:
        """Arranca/recarga la partida `game` para la sesion dada."""

    @abstractmethod
    def send_command(self, session_id: str, command: str) -> EngineResult:
        """Envia un comando textual al motor y devuelve su salida real."""

    @abstractmethod
    def close_game(self, session_id: str) -> None:
        """Cierra la partida y libera recursos de la sesion."""

    def get_state(self, session_id: str) -> EngineResult:
        """Estado actual. Por defecto se modela como un `look`."""
        return self.send_command(session_id, "look")

    def move(self, session_id: str, direction: str) -> EngineResult:
        """Movimiento semantico. Cada motor traduce a su dialecto."""
        return self.send_command(session_id, f"go {direction}")
