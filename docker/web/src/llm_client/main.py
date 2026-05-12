import json
from src.llm_client.llm import call_llm
from src.llm_client.mcp_client import call_tool
def main():
    print("=== Cliente LLM + MCP ===")

    while True:
        user_input = input("\n>>> ")

        if user_input.lower() in ["exit", "quit"]:
            break

        messages = [
            {
                "role": "system",
                "content": "Eres un agente que juega a una aventura de texto. Usa las herramientas disponibles (new_game, look, move) para interactuar con el juego. No inventes acciones, usa siempre las tools cuando sea necesario."
            },
            {"role": "user", "content": user_input}
        ]

        print("\n[DEBUG] Enviando al LLM...")

        response = call_llm(messages)

        print("\n[DEBUG] Respuesta RAW:")
        print(json.dumps(response, indent=2))

        # ⚠️ Extraer mensaje de forma segura
        choices = response.get("choices", [])
        if not choices:
            print("[ERROR] No hay 'choices' en la respuesta")
            continue

        msg = choices[0].get("message", {})

        #  CASO 1: TOOL CALL
        if "tool_calls" in msg:
            print("\n[DEBUG] Tool call detectado")

            tool_call = msg["tool_calls"][0]
            tool_name = tool_call["function"]["name"]

            try:
                args = json.loads(tool_call["function"].get("arguments", "{}"))
            except:
                args = {}

            print(f"[DEBUG] Ejecutando tool: {tool_name} con args: {args}")

            result = call_tool(tool_name, args)

            print(f"[DEBUG] Resultado tool: {result}")

            # Añadir al historial
            messages.append(msg)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],   
                "content": str(result)
            })

            print("\n[DEBUG] Reenviando resultado al LLM...")

            # 2ª llamada
            response2 = call_llm(messages)

            print("\n[DEBUG] Respuesta final RAW:")
            print(json.dumps(response2, indent=2))

            choices2 = response2.get("choices", [])
            if not choices2:
                print("[ERROR] No hay respuesta final")
                continue

            final_msg = choices2[0].get("message", {})
            print("\n🤖", final_msg.get("content", "SIN RESPUESTA"))

        #  CASO 2: RESPUESTA NORMAL
        else:
            print("\n🤖", msg.get("content", "SIN RESPUESTA"))


if __name__ == "__main__":
    main()