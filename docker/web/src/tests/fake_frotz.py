#!/usr/bin/env python3
"""Interprete Z-machine FALSO para tests (sin jericho ni frotz real).

Imita a `dfrotz` dumb: imprime texto y un prompt ">" SIN salto final, y lee una
linea por stdin. Ignora los flags de dfrotz. Implementa un mini-juego determinista
(casa + buzon) suficiente para ejercitar FrotzEngine en CI."""
import sys

loc = 0
def room():
    if loc == 0:
        return "West of House\nA small mailbox is here.\nExits: north."
    return "North of House\nExits: south."

def emit(text, prompt=True):
    sys.stdout.write(text.rstrip("\n") + "\n")
    if prompt:
        sys.stdout.write(">")
    sys.stdout.flush()

emit("FAKE FROTZ TEST GAME\n" + room())
for line in sys.stdin:
    c = line.strip().lower()
    if c in ("quit", "q"):
        emit("Bye.", prompt=False); break
    elif c in ("look", "l"):
        emit(room())
    elif c in ("north", "n"):
        loc = 1; emit(room())
    elif c in ("south", "s"):
        loc = 0; emit(room())
    elif c == "open mailbox":
        emit("Opening the mailbox reveals a leaflet." if loc == 0 else "There is no mailbox here.")
    else:
        emit("I don't understand.")
