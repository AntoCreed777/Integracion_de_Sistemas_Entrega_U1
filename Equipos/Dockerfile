# Etapa 1: Base comun y servicio para produccion
FROM python:3.12-slim as base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/src:/src/app:/src/generated"

WORKDIR /src

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN wget -qO /bin/grpc_health_probe \
    https://github.com/grpc-ecosystem/grpc-health-probe/releases/download/v0.4.55/grpc_health_probe-linux-amd64 \
    && chmod +x /bin/grpc_health_probe

# Para no copiar los archivos de test, se copian explicitamente los archivos necesarios
COPY app/ ./app/
COPY equipos.proto generar_grpc.py ./

RUN python generar_grpc.py

HEALTHCHECK \
  --start-period=5s \
  --interval=5s \
  --timeout=3s \
  --retries=3 \
  CMD /bin/grpc_health_probe -addr=:50051

EXPOSE 50051

CMD ["python", "-m", "app.main"]


# Etapa 2: Servicio para test
FROM base as test

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY tests/ ./tests/
COPY pytest.ini ./

# Se sobreescriben
HEALTHCHECK NONE
CMD ["sh", "-c", "python -m app.init_db && pytest"]