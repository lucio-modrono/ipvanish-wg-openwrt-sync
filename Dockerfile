FROM python:3.9-slim

# Instalar dependencias mínimas para la instalación
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 1. Descargar la llave GPG real de Google (URL correcta)
RUN curl -fSsL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg

# 2. Añadir el repositorio oficial de Chrome
RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://google.com stable main" > /etc/apt/sources.list.d/google-chrome.list

# 3. Instalar Chrome y limpiar herramientas de instalación para reducir tamaño
RUN apt-get update && apt-get install -y --no-install-recommends \
    google-chrome-stable \
    && apt-get purge -y --auto-remove wget gnupg \
    && rm -rf /var/lib/apt/lists/*

# Definir la ruta del binario de Chrome
ENV CHROME_BIN=/usr/bin/google-chrome-stable \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
CMD ["python", "main.py"]
