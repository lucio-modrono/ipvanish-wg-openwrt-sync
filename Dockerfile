FROM python:3.9-slim

# Instalar dependencias necesarias para manejar repositorios y Chrome
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    unzip \
    ca-certificates \
    --no-install-recommends

# 1. Descargar la llave de Google y guardarla en el nuevo formato (GPG)
RUN wget -q -O - https://google.com | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg

# 2. Añadir el repositorio de Google usando la llave específica
RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://google.com stable main" > /etc/apt/sources.list.d/google-chrome.list

# 3. Instalar Google Chrome y limpiar archivos temporales
RUN apt-get update && apt-get install -y \
    google-chrome-stable \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Definir la ruta del binario de Chrome
ENV CHROME_BIN=/usr/bin/google-chrome-stable \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
CMD ["python", "main.py"]
