# Juegos Z-machine (motor Frotz)

Este directorio contiene los ficheros de historia (.z3/.z5) que ejecuta el
motor **Frotz** (`dfrotz`, interfaz dumb) dentro del contenedor `web-app`.

## Incluido y listo para jugar

- **`minizork.z5`** — mundo de demostracion **original** (texto propio, sin
  copyright de Infocom), compilado con Inform 6. Sirve para validar de
  extremo a extremo el motor Frotz: tiene casa, buzon, folleto y movimiento.
  Fuente incluida en `minizork.inf`.
  Catalogo: id `minizork`.

## Anadir Zork I (opcional)

El binario original de Zork es propiedad de Activision, por eso **no se
incluye**. Para jugarlo:

1. **No necesitas ZILF para jugar**, solo un fichero Z-machine y Frotz.
2. Si quieres generarlo de forma limpia: el codigo fuente ZIL de Zork I-III es
   open source (2025). Compila con ZILF/ZAPF:
   ```bash
   zilf build zork1.zil      # produce zork1.zap ...
   zapf zork1.zap            # produce zork1.z3
   ```
3. Coloca el resultado aqui como **`zork1.z3`** (o ajusta `ZORK1_PATH`).
   El catalogo ya tiene la entrada `zork1` apuntando a `/app/games/zmachine/zork1.z3`.

Cualquier `.z3/.z5/.z8` valido funciona: basta anadir una entrada en
`docker/web/src/llm_client/catalog.py` con `engine="frotz"` y su ruta.
