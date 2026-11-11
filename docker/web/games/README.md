# Carpeta de juegos (drop-in)

Deja aquí un fichero de juego y aparecerá **automáticamente** en el menú
(`list_games`), sin tocar código. Con `docker compose up`, esta carpeta está
montada como volumen, así que basta con copiar el fichero y recargar; no hace
falta reconstruir la imagen.

## Dónde va cada cosa (según la extensión)

| Carpeta        | Motor  | Extensiones aceptadas                                  |
|----------------|--------|--------------------------------------------------------|
| `zmachine/`    | Frotz  | `.z1` `.z2` `.z3` `.z4` `.z5` `.z6` `.z7` `.z8` `.zblorb` `.zlb` `.dat` |
| `quest/`       | Quest  | `.quest`                                               |

El `id` del juego se deriva del nombre del fichero (p.ej. `zork1.z3` → id
`zork1`). Para Zork I–III el menú ya les pone nombre bonito ("Zork I", etc.).

## Ejemplos

- Copia `zork1.z3` en `zmachine/` → en la web: *"juega a zork1"*.
- Copia `mi_aventura.quest` en `quest/` → *"juega a mi_aventura"*.

> Incluidos: `zmachine/minizork.z5` y `zmachine/cave.z5` (juegos de demostración
> propios) y `zmachine/zork1.z3` (Zork I, compilado con ZILF a partir de su
> código fuente, publicado con licencia MIT). Véase `zmachine/README.md`.
>
> Limitación de Quest: el reproductor carga automáticamente el juego configurado
> en `docker-compose.yaml`, así que un `.quest` copiado en `quest/` aparece en el
> menú pero no llega a cargarse (capítulo 6 de la memoria).
