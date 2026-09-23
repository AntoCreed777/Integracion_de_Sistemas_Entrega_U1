FROM python:3.12-slim AS base

WORKDIR /app

# Instalar dependencias del sistema necesarias para psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# 1. Crea la carpeta y su __init__.py para que Python lo reconozca como módulo
RUN mkdir -p app/generated && touch app/generated/__init__.py

# 2. Compila el archivo .proto al vuelo
RUN python -m grpc_tools.protoc \
    -I. \
    --python_out=app/generated \
    --grpc_python_out=app/generated \
    equipos.proto \
&& sed -i 's/^import equipos_pb2 as equipos__pb2/from . import equipos_pb2 as equipos__pb2/' app/generated/equipos_pb2_grpc.py
# Exponer el puerto donde correrá Uvicorn
EXPOSE 8080


HEALTHCHECK \
    --interval=10s \
    --timeout=5s \
    --start-period=15s \
    --retries=5 \
    CMD curl -f http://localhost:8080/health || exit 1

# Comando para levantar FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

FROM base AS test

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY tests/ ./tests/
COPY pytest.ini .

HEALTHCHECK NONE
CMD ["pytest"]