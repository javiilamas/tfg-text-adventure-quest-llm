
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class Room:
    desc: str
    exits: Dict[str, str]
    items: List[str]

@dataclass
class World:
    meta: Dict[str, Any]
    start: Dict[str, Any]
    rooms: Dict[str, Room]
    items: Dict[str, Dict[str, Any]]
    rules: List[Dict[str, Any]]

@dataclass
class GameState:
    room: str
    inventory: List[str] = field(default_factory=list)
    flags: Dict[str, Any] = field(default_factory=dict)
    room_items: Dict[str, List[str]] = field(default_factory=dict)
