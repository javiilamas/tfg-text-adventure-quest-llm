
import shlex
from pathlib import Path
import typer
from engine.loader import load_json, validate_world, build_world, bootstrap_state
from engine.engine import look, move, take, drop, use, state_view

app = typer.Typer(help="Text adventure CLI (Hito 1)")

@app.command()
def play(world: Path = typer.Option(..., exists=True, help="Ruta a world.json"),
         schema: Path = typer.Option("worlds/world_schema.json", exists=True)):
    wd = load_json(world)
    validate_world(wd, schema)
    world_obj = build_world(wd)
    state = bootstrap_state(world_obj)
    print("¡Bienvenido! Comandos: look | move north | take key | drop key | use key door | state | quit")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAdiós.")
            break
        if not line:
            continue
        if line in ("quit","exit"):
            print("Adiós.")
            break
        tokens = shlex.split(line)
        cmd = tokens[0].lower()
        args = tokens[1:]
        if cmd == "look":
            resp = look(world_obj, state)
        elif cmd == "move" and args:
            resp = move(world_obj, state, args[0])
        elif cmd == "take" and args:
            resp = take(world_obj, state, args[0])
        elif cmd == "drop" and args:
            resp = drop(world_obj, state, args[0])
        elif cmd == "use" and args:
            item = args[0]
            target = args[1] if len(args) > 1 else None
            resp = use(world_obj, state, item, target)
        elif cmd == "state":
            resp = state_view(world_obj, state)
        else:
            print("Comando no reconocido.")
            continue

        if resp.get("ok"):
            if resp.get("narration"):
                print(resp["narration"])
        else:
            err = resp.get("error", {})
            print(f"[{err.get('code','ERROR')}] {err.get('message','')}")

if __name__ == "__main__":
    app()
