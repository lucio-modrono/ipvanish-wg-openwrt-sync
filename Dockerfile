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
RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# 3. Instalar Chrome y crear enlace simbólico
RUN apt-get update && apt-get install -y --no-install-recommends \
    google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 4. Verificación de seguridad: si el binario no existe, el build fallará aquí
RUN ls -l /usr/bin/google-chrome

ENV CHROME_BIN=/usr/bin/google-chrome \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
CMD ["python", "main.py"]
