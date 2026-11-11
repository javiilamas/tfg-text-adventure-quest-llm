# Juegos Z-machine (motor Frotz)

Ficheros de historia que ejecuta `dfrotz`. Cualquier `.z3`, `.z5`, etc. copiado
en esta carpeta aparece en el menú sin tocar código (véase `../README.md`).

## Incluidos

| Fichero | Juego | Origen |
| --- | --- | --- |
| `minizork.z5` | MiniZork | Juego de demostración propio; fuente en `minizork.inf` (Inform 6) |
| `cave.z5` | La Cueva | Juego de demostración propio; fuente en `cave.inf` (Inform 6) |
| `zork1.z3` | Zork I | Compilado con ZILF 1.9.0 el 30/06/2026 a partir del código fuente de Zork I, que Microsoft publicó con licencia MIT en noviembre de 2025. La licencia está en `LICENSE-zork1.txt` |

## Compilar Zork I, II y III

No hace falta ZILF para jugar, solo el fichero de historia y Frotz. Para
generarlo, se compila el código fuente ZIL con [ZILF](https://zilf.io) y su
ensamblador ZAPF:

```bash
zilf zork1.zil      # genera zork1.zap
zapf zork1.zap      # genera zork1.z3
```

El código de Zork I viene como ejemplo en la distribución de ZILF (carpeta
`sample/zork1`) y está también en <https://github.com/historicalsource/zork1>;
el de Zork II y Zork III, en los repositorios `zork2` y `zork3` de la misma
organización. El fichero resultante se copia en esta carpeta.
