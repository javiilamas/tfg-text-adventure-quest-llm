tools = [
    {
        "type": "function",
        "function": {
            "name": "new_game",
            "description": "Inicia una nueva partida en el juego",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "look",
            "description": "Describe el entorno actual",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move",
            "description": "Moverse en una dirección",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["north", "south", "east", "west"]
                    }
                },
                "required": ["direction"]
            }
        }
    }
]