# Usamos Python Alpine para el mínimo tamaño posible
FROM python:3.9-alpine

# 1. Instalar dependencias del sistema y Chromium
# Instala Chromium y su driver, además de librerías para Paramiko (Cffi/Cryptography)
RUN apk add --no-cache \
    openssl \
    ca-certificates \
    chromium \
    chromium-chromedriver \
    libffi-dev \
    openssl-dev \
    gcc \
    musl-dev \
    make \
    python3-dev

# 2. Configurar variables de entorno para Selenium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 3. Instalar librerías de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Limpiar dependencias de compilación para ahorrar espacio
RUN apk del libffi-dev openssl-dev gcc musl-dev make

# 5. Copiar script
COPY main.py .

CMD ["python", "main.py"]
