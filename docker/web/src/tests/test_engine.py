"""Tests offline del nucleo multi-motor. No requieren frotz real ni red:
usan fake_frotz.py como interprete. Ejecutar dentro del contenedor web:

    docker compose run --rm web-app python -m unittest discover -s src/tests
"""
import os
import sys
import json
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # docker/web
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FAKE = os.path.join(os.path.dirname(__file__), "fake_frotz.py")
os.environ.setdefault("OPENROUTER_API_KEY", "dummy")

from src.llm_client.engines.frotz_engine import FrotzEngine          # noqa: E402
from src.llm_client.catalog import GameSpec                          # noqa: E402
import src.llm_client.catalog as catalog                             # noqa: E402
from src.llm_client import mcp_client                                # noqa: E402


class FrotzEngineTest(unittest.TestCase):
    def setUp(self):
        self.eng = FrotzEngine(frotz_bin=FAKE)
        self.game = GameSpec("fake", "Fake", "frotz", "/dev/null")

    def test_start_look_move_close(self):
        r = self.eng.start_game("s1", self.game)
        self.assertTrue(r.ok, r.error)
        self.assertIn("West of House", r.output)
        self.assertIn("leaflet", self.eng.send_command("s1", "open mailbox").output)
        self.assertIn("North of House", self.eng.move("s1", "north").output)
        self.eng.close_game("s1")
        self.assertFalse(self.eng.send_command("s1", "look").ok)

    def test_sessions_isolated(self):
        self.eng.start_game("a", self.game)
        self.eng.start_game("b", self.game)
        self.eng.move("a", "north")                  # a -> North
        self.assertIn("North of House", self.eng.send_command("a", "look").output)
        self.assertIn("West of House", self.eng.send_command("b", "look").output)  # b intact
        self.eng.close_game("a"); self.eng.close_game("b")


class CatalogDiscoveryTest(unittest.TestCase):
    def test_discovery_by_extension(self):
        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, "zmachine"))
        os.makedirs(os.path.join(tmp, "quest"))
        open(os.path.join(tmp, "zmachine", "zork1.z3"), "w").close()
        open(os.path.join(tmp, "zmachine", "ignore.txt"), "w").close()
        open(os.path.join(tmp, "quest", "demo.quest"), "w").close()
        catalog.GAMES_ROOT = tmp
        games = {g["id"]: g for g in catalog.list_games()}
        self.assertEqual(games["zork1"]["engine"], "frotz")
        self.assertEqual(games["zork1"]["name"], "Zork I")
        self.assertEqual(games["demo"]["engine"], "quest")
        self.assertNotIn("ignore", games)
        self.assertIn("quest_tutorial", games)       # incorporado sigue


class RouterTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, "zmachine"))
        open(os.path.join(tmp, "zmachine", "fake.z5"), "w").close()
        catalog.GAMES_ROOT = tmp
        os.environ["FROTZ_BIN"] = FAKE
        # nuevo MANAGER que use el FROTZ_BIN del fake
        import importlib
        from src.llm_client import sessions as sess
        importlib.reload(sess)
        mcp_client.MANAGER = sess.MANAGER

    def test_router_flow(self):
        self.assertTrue(any(g["id"] == "fake" for g in mcp_client.call_tool("list_games", {})["games"]))
        r = mcp_client.call_tool("start_game", {"game_id": "fake"}, session_id="r1")
        self.assertTrue(r.get("ok"), r)
        self.assertIn("leaflet", mcp_client.call_tool(
            "send_game_command", {"command": "open mailbox"}, session_id="r1")["output"])
        self.assertEqual(mcp_client.call_tool("current_game", {}, session_id="r1")["game_id"], "fake")
        mcp_client.call_tool("close_game", {}, session_id="r1")


class RepairHistoryTest(unittest.TestCase):
    def test_repair_orphan(self):
        try:
            from src.web_app.app import _repair_history
        except Exception as e:
            self.skipTest(f"flask no disponible: {e}")
        poisoned = [
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "X", "function": {"name": "f", "arguments": "{}"}}]},
            {"role": "user", "content": "hola"},
        ]
        fixed = _repair_history(poisoned)
        self.assertTrue(any(m.get("role") == "tool" and m.get("tool_call_id") == "X" for m in fixed))
        self.assertEqual(_repair_history(fixed), fixed)  # idempotente


if __name__ == "__main__":
    unittest.main(verbosity=2)
