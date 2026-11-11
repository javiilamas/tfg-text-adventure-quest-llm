FROM python:3.11-slim

WORKDIR /app

# Frotz: el paquete 'frotz' de Debian instala el binario 'dfrotz' (interfaz
# dumb) en /usr/games/. coreutils aporta 'stdbuf' (mitiga el full-buffering).
RUN apt-get update \
    && apt-get install -y --no-install-recommends frotz coreutils \
    && rm -rf /var/lib/apt/lists/*

# /usr/games no esta en el PATH de la imagen slim: fijamos la ruta del binario.
ENV PATH="/usr/games:${PATH}" \
    FROTZ_BIN="/usr/games/dfrotz"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "src.web_app.app"]
