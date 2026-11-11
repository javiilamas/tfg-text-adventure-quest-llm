"""Tests de la capa web (bucle de tool-calling) SIN red ni LLM real.

Se sustituye call_llm por un modelo simulado y call_tool por una tool falsa, de
modo que se prueba exactamente el codigo de app.py:
  * RNF2: dos envios simultaneos en la misma sesion no corrompen el historial.
  * Limite de pasos (LLM_MAX_STEPS) ante un modelo que no deja de pedir tools.
  * Error del proveedor -> mensaje controlado, sin excepcion.

    python -m unittest src.tests.test_web_robustez -v
"""
import os
import sys
import json
import time
import threading
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("OPENROUTER_API_KEY", "dummy")
os.environ["DEBUG_LLM"] = "0"

try:
    from src.web_app import app as webapp
except Exception as e:  # flask no instalado
    webapp = None
    _IMPORT_ERROR = e


def _llm_simulado(messages):
    """Si lo ultimo es del usuario, pide una tool; si es un resultado, responde."""
    time.sleep(0.2)  # ensancha la ventana de carrera
    last = messages[-1]
    if last.get("role") == "user":
        return {"choices": [{"message": {
            "role": "assistant", "content": None,
            "tool_calls": [{"id": f"call_{time.time_ns()}", "type": "function",
                            "function": {"name": "look", "arguments": "{}"}}]}}]}
    return {"choices": [{"message": {"role": "assistant", "content": "Estas al oeste de la casa."}}]}


def _tool_falsa(name, args, session_id="web"):
    return {"ok": True, "output": "West of House"}


def _historial_valido(messages) -> bool:
    """Cada assistant con tool_calls va seguido de un 'tool' por cada id."""
    i = 0
    while i < len(messages):
        m = messages[i]
        if m.get("role") == "assistant" and m.get("tool_calls"):
            ids = {tc["id"] for tc in m["tool_calls"]}
            j = i + 1
            vistos = set()
            while j < len(messages) and messages[j].get("role") == "tool":
                vistos.add(messages[j]["tool_call_id"])
                j += 1
            if ids != vistos:
                return False
            i = j
        else:
            i += 1
    return True


@unittest.skipIf(webapp is None, "flask no disponible")
class WebLoopTest(unittest.TestCase):
    def setUp(self):
        webapp._STATE.clear()
        webapp.app.config["TESTING"] = True

    def _cliente(self, sid):
        c = webapp.app.test_client()
        with c.session_transaction() as s:
            s["sid"] = sid
        return c

    def test_doble_envio_concurrente(self):
        """Dos POST a la vez con la misma cookie: el lock los serializa."""
        with mock.patch.object(webapp, "call_llm", _llm_simulado), \
             mock.patch.object(webapp, "call_tool", _tool_falsa):
            c1, c2 = self._cliente("S"), self._cliente("S")
            codes = []
            hilos = [threading.Thread(target=lambda c=c: codes.append(
                c.post("/", data={"message": "mira"}).status_code)) for c in (c1, c2)]
            for h in hilos:
                h.start()
            for h in hilos:
                h.join()
        st = webapp._STATE["S"]
        self.assertEqual(codes, [200, 200])
        self.assertTrue(_historial_valido(st["messages"]))
        # 2 turnos completos: user, assistant(tool_calls), tool, assistant(final)
        self.assertEqual([m["role"] for m in st["chat"]], ["user", "assistant"] * 2)

    def test_limite_de_pasos(self):
        """Un modelo que siempre pide tools se corta en LLM_MAX_STEPS llamadas."""
        llamadas = []

        def siempre_tool(messages):
            llamadas.append(1)
            return {"choices": [{"message": {"role": "assistant", "content": None,
                    "tool_calls": [{"id": f"c{len(llamadas)}", "type": "function",
                                    "function": {"name": "look", "arguments": "{}"}}]}}]}

        with mock.patch.object(webapp, "call_llm", siempre_tool), \
             mock.patch.object(webapp, "call_tool", _tool_falsa):
            webapp._state("L")["messages"].append({"role": "user", "content": "hola"})
            txt = webapp.run_llm_tool_loop("L", max_steps=4)
        self.assertEqual(len(llamadas), 4)
        self.assertIn("bucle", txt)
        self.assertTrue(_historial_valido(webapp._STATE["L"]["messages"]))

    def test_error_del_proveedor(self):
        err = {"error": {"message": "Rate limit", "code": 429}}
        with mock.patch.object(webapp, "call_llm", lambda m: err):
            webapp._state("E")["messages"].append({"role": "user", "content": "hola"})
            txt = webapp.run_llm_tool_loop("E")
        self.assertTrue(txt.startswith("Error en la llamada al LLM"))

    def test_argumentos_json_invalidos(self):
        """Si el modelo manda arguments mal formados, la tool recibe {}."""
        recibidos = []

        def llm(messages):
            if messages[-1]["role"] == "user":
                return {"choices": [{"message": {"role": "assistant", "content": None,
                        "tool_calls": [{"id": "x", "type": "function",
                                        "function": {"name": "move", "arguments": "{no json"}}]}}]}
            return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

        def tool(name, args, session_id="web"):
            recibidos.append(args)
            return {"ok": True}

        with mock.patch.object(webapp, "call_llm", llm), mock.patch.object(webapp, "call_tool", tool):
            webapp._state("J")["messages"].append({"role": "user", "content": "norte"})
            self.assertEqual(webapp.run_llm_tool_loop("J"), "ok")
        self.assertEqual(recibidos, [{}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
