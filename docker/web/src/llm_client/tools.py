"""Esquemas de tools expuestos al LLM (formato OpenAI/OpenRouter).

Estrategia combinada:
  * Tools de MENU (gestionan que motor/juego esta activo): list_games,
    start_game, current_game, close_game.
  * Tool generica de juego: send_game_command (el parser del juego, que es la
    fuente de verdad, interpreta el texto).
  * Atajos semanticos opcionales: look, move (y new_game por compatibilidad).
Seguridad: send_game_command SOLO escribe en la entrada del proceso del juego;
nunca ejecuta comandos del sistema.
"""

tools = [
    {
        "type": "function",
        "function": {
            "name": "list_games",
            "description": "Lista los juegos disponibles (id, nombre y motor). Usar cuando el usuario pregunte a que puede jugar o quiera elegir juego.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_game",
            "description": "Inicia (o reinicia) un juego concreto por su id. Devuelve el texto inicial real del motor. Llama antes a list_games si no conoces el id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "game_id": {
                        "type": "string",
                        "description": "Id del juego del catalogo, p.ej. 'quest_tutorial', 'minizork', 'zork1'.",
                    }
                },
                "required": ["game_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "current_game",
            "description": "Devuelve que juego y que motor estan activos en la sesion actual.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_game",
            "description": "Cierra la partida activa y libera recursos del motor.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_game_command",
            "description": "Envia un comando textual al juego activo en el lenguaje del propio juego (p.ej. 'open mailbox', 'read leaflet', 'east', 'take lamp'). Es la herramienta principal para jugar. El resultado es la salida real del motor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Comando en el dialecto del juego.",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "look",
            "description": "Atajo: describe el entorno actual del juego activo.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move",
            "description": "Atajo: moverse en una direccion. El motor traduce al dialecto correcto (Quest: 'go east'; Frotz: 'east').",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["north", "south", "east", "west", "up", "down"],
                    }
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "new_game",
            "description": "Reinicia el juego actual; si no hay ninguno, inicia el tutorial de Quest. (Compatibilidad con la version anterior.)",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
