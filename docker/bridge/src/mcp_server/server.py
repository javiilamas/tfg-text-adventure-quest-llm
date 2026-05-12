# src/mcp_server/server.py
from __future__ import annotations
from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

import os
import httpx
from mcp.server.fastmcp import FastMCP

from src.engine.loader import load_json, validate_world, build_world, bootstrap_state
from src.engine.engine import (
    look as eng_look,
    move as eng_move,
    take as eng_take,
    drop as eng_drop,
    use as eng_use,
    state_view as eng_state,
)

# MCP app
mcp = FastMCP("tfg-text-adventure")

import sys
print("LO MAS NUEVO", file=sys.stderr)
BRIDGE_BASE = "http://127.0.0.1:8787"
DEFAULT_QUEST_PATH = r"C:\Users\lecle\Desktop\TFG\tfg-text-adventure-with-tests\src\quest-juegos\juego_prueba.quest"
# --- Sesiones ---
class Session:
    def __init__(self, world_dict: Dict[str, Any], schema_path: str):
        validate_world(world_dict, schema_path)
        self.world = build_world(world_dict)
        self.state = bootstrap_state(self.world)

SESSIONS: Dict[str, Session] = {}

def get_session(session_id: str) -> Session:
    if session_id not in SESSIONS:
        raise RuntimeError("SESSION_NOT_FOUND")
    return SESSIONS[session_id]

##HELPER PARA LLAMAR AL BRIDGE
async def bridge_post(path: str, payload: dict):
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{BRIDGE_BASE}{path}", json=payload)
        r.raise_for_status()
        return r.json()


# --- Tools MCP ---


class NewGameArgs(BaseModel):
    sessionId: str = Field(..., min_length=1)
    questPath: Optional[str] = None  # opcional, por si quieres cambiar juego

class StateArgs(BaseModel):
    sessionId: str

class MoveArgs(BaseModel):
    sessionId: str
    direction: Literal["north","south","east","west"]

class TakeArgs(BaseModel):
    sessionId: str
    item: str

class DropArgs(BaseModel):
    sessionId: str
    item: str

class UseArgs(BaseModel):
    sessionId: str
    item: str
    target: Optional[str] = None


@mcp.tool()

async def new_game(sessionId: str, questPath: Optional[str] = None):
    quest_file = questPath or DEFAULT_QUEST_PATH
    return await bridge_post(
        "/session/new",
        {"sessionId": sessionId, "questFilePath": quest_file}
    )

@mcp.tool()
async def look(args: StateArgs):
    return await bridge_post("/session/command", {"sessionId": args.sessionId, "text": "look"})


@mcp.tool()
async def move(args: MoveArgs):
    # El parser de Quest suele aceptar "go north" y también "north".
    cmd = f"go {args.direction}"
    return await bridge_post("/session/command", {"sessionId": args.sessionId, "text": cmd})


@mcp.tool()
async def take(args: TakeArgs):
    return await bridge_post("/session/command", {"sessionId": args.sessionId, "text": f"take {args.item}"})


@mcp.tool()
async def drop(args: DropArgs):
    return await bridge_post("/session/command", {"sessionId": args.sessionId, "text": f"drop {args.item}"})


@mcp.tool()
async def use(args: UseArgs):
    # Si hay target: "use key on door" (o "unlock door with key" según juego)
    if args.target:
        cmd = f"use {args.item} on {args.target}"
    else:
        cmd = f"use {args.item}"
    return await bridge_post("/session/command", {"sessionId": args.sessionId, "text": cmd})


@mcp.tool()
async def state(args: StateArgs):
    # Por ahora devolvemos el "body" que trae el bridge (luego lo refinamos)
    return await bridge_post("/session/command", {"sessionId": args.sessionId, "text": "look"})

if __name__ == "__main__":
    mcp.run()