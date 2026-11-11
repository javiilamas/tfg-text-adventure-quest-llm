"""Tests de seguridad (RNF4).

  * Router: el LLM solo puede elegir juegos por id; nunca ve ni pasa rutas.
  * FrotzEngine con dfrotz REAL (se salta si no esta instalado):
      - los metacaracteres de shell llegan al parser del juego como texto;
      - un salto de linea no permite colar un segundo comando;
      - SAVE no puede escribir fuera del directorio confinado con -R.

    python -m unittest src.tests.test_seguridad -v
"""
import os
import sys
import shutil
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("OPENROUTER_API_KEY", "dummy")

from src.llm_client.engines import frotz_engine                # noqa: E402
from src.llm_client.engines.frotz_engine import FrotzEngine   # noqa: E402
from src.llm_client.catalog import GameSpec                   # noqa: E402
import src.llm_client.catalog as catalog                      # noqa: E402
from src.llm_client import mcp_client                         # noqa: E402

DFROTZ = os.getenv("FROTZ_BIN") if os.getenv("FROTZ_BIN", "").endswith("dfrotz") else None
DFROTZ = DFROTZ or shutil.which("dfrotz") or ("/usr/games/dfrotz" if os.path.exists("/usr/games/dfrotz") else None)
MINIZORK = os.path.join(ROOT, "games", "zmachine", "minizork.z5")
ZORK1 = os.path.join(ROOT, "games", "zmachine", "zork1.z3")


class RouterSeguridadTest(unittest.TestCase):
    def test_list_games_no_expone_rutas(self):
        for g in mcp_client.call_tool("list_games", {})["games"]:
            self.assertNotIn("path", g)
            self.assertFalse(any("/" in str(v) or "\\" in str(v) for v in g.values()), g)

    def test_game_id_con_ruta_se_rechaza(self):
        r = mcp_client.call_tool("start_game", {"game_id": "../../etc/passwd"}, session_id="x")
        self.assertFalse(r["ok"])
        self.assertTrue(r["error"].startswith("UNKNOWN_GAME"))

    def test_comando_saneado(self):
        """Caracteres de control fuera, longitud limitada y move restringido a
        las direcciones de su esquema (correcciones de Frotz v6)."""
        if not hasattr(mcp_client, "_sanitize"):
            self.skipTest("parche de saneado no aplicado")
        self.assertEqual(mcp_client._sanitize("\x1b[2J\x07look"), "[2Jlook")
        self.assertEqual(len(mcp_client._sanitize("x" * 500)), mcp_client.MAX_COMMAND_LEN)
        # move: el enrutador admite exactamente las direcciones del esquema...
        from src.llm_client.tools import tools
        esquema = next(t["function"] for t in tools if t["function"]["name"] == "move")
        self.assertEqual(list(mcp_client.MOVE_DIRECTIONS),
                         esquema["parameters"]["properties"]["direction"]["enum"])
        # ...y rechaza cualquier otro texto antes de que llegue al motor.
        for mala in ("north; touch /tmp/x", "look", "", None):
            r = mcp_client.call_tool("move", {"direction": mala}, session_id="x")
            self.assertEqual(r.get("error"), "INVALID_direction", mala)

    def test_tool_desconocida(self):
        r = mcp_client.call_tool("run_shell", {"cmd": "ls"}, session_id="x")
        self.assertEqual(r["error"], "UNKNOWN_TOOL: run_shell")


@unittest.skipUnless(DFROTZ and os.path.exists(MINIZORK), "dfrotz real o minizork.z5 no disponibles")
class FrotzRealSeguridadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.eng = FrotzEngine(frotz_bin=DFROTZ, save_root=os.path.join(self.tmp, "saves"))
        r = self.eng.start_game("s", GameSpec("minizork", "MiniZork", "frotz", MINIZORK))
        self.assertTrue(r.ok, r.error)

    def tearDown(self):
        self.eng.close_game("s")
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_metacaracteres_de_shell_son_texto(self):
        canario = os.path.join(self.tmp, "PWNED")
        for cmd in (f"; touch {canario}", f"$(touch {canario})", f"`touch {canario}`",
                    f"| touch {canario}", f"&& touch {canario}"):
            r = self.eng.send_command("s", cmd)
            self.assertTrue(r.ok)
        self.assertFalse(os.path.exists(canario))
        self.assertIsNone(self.eng._get("s").proc.poll())   # el juego sigue vivo

    def test_salto_de_linea_no_cuela_otro_comando(self):
        self.eng.send_command("s", "look\nquit")              # se envia como UNA linea
        self.assertIsNone(self.eng._get("s").proc.poll())
        self.assertIn("West of House", self.eng.send_command("s", "look").output)


@unittest.skipUnless(DFROTZ and os.path.exists(ZORK1), "dfrotz real o zork1.z3 no disponibles")
class SaveConfinadoTest(unittest.TestCase):
    def test_save_no_sale_del_directorio(self):
        if not hasattr(frotz_engine, "_INTERP_PROMPT"):
            self.skipTest("sin el parche, cada prompt de SAVE espera 12 s")
        tmp = tempfile.mkdtemp()
        eng = FrotzEngine(frotz_bin=DFROTZ, save_root=os.path.join(tmp, "saves"))
        eng.start_game("z", GameSpec("zork1", "Zork I", "frotz", ZORK1))
        self.assertIn("filename", eng.send_command("z", "save").output)
        fuera = os.path.join(tmp, "fuera")
        self.assertIn("Ok", eng.send_command("z", "../../../.." + fuera).output)
        eng.close_game("z")
        self.assertFalse(os.path.exists(fuera) or os.path.exists(fuera + ".qzl"))
        # Frotz 2.54 guarda "fuera"; Frotz 2.55 añade la extensión: "fuera.qzl".
        dentro = os.path.join(tmp, "saves", "z", "fuera")
        self.assertTrue(os.path.exists(dentro) or os.path.exists(dentro + ".qzl"))
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
