# Juegos Z-machine (motor Frotz)

Ficheros de historia que ejecuta `dfrotz`. **Drop-in**: copia aquí un `.z3/.z5/...`
y aparece solo en el menú (ver `../README.md`).

## Incluido
- `minizork.z5` — demo **original** (sin copyright), fuente en `minizork.inf`.

## Añadir Zork I–III
No necesitas ZILF para *jugar*, solo el fichero `.z3/.z5` y Frotz. Para generarlos
de forma limpia, su código fuente ZIL es abierto; compílalo con ZILF/ZAPF:
```bash
zilf build zork1.zil      # -> zork1.zap ...
zapf zork1.zap            # -> zork1.z3
```
Copia el resultado aquí (`zork1.z3`, `zork2.z3`, `zork3.z3`) y listo.
