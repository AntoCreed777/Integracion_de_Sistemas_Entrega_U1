# Cliente gRPC en Node.js

Este cliente demuestra interoperabilidad entre Node.js y el servicio gRPC de
Equipos implementado en Python. Carga directamente el archivo
[`../Equipos/equipos.proto`](../Equipos/equipos.proto), por lo que no necesita
código generado manualmente.

## Requisitos

- Node.js 18+
- El servicio `equipos-api` corriendo en `localhost:50051` o en la red Docker
  con el nombre `equipos-api:50051`.

## Instalación

```bash
cd cliente-node
npm install
```

## Uso

```bash
node src/index.js consultar 1
node src/index.js disponibilidad 1
node src/index.js listar
node src/index.js reservar 1
node src/index.js liberar 1
node src/index.js demo 1
```

También puedes usar los scripts de `package.json`:

```bash
npm run consultar -- 1
npm run disponibilidad -- 1
npm run listar
npm run reservar -- 1
npm run liberar -- 1
npm run demo -- 1
```

## Ejecutarlo contra Docker

Desde la raíz del proyecto:

```bash
cp .env.example .env
```

Y luego levanta solo los servicios necesarios:

```bash
docker compose up -d equipos-db equipos-api
```

Después, desde `cliente-node`:

```bash
EQUIPOS_GRPC_URL=localhost:50051 npm run demo -- 1
```

Si el cliente corre dentro de la misma red Docker, usa:

```bash
EQUIPOS_GRPC_URL=equipos-api:50051 npm run demo -- 1
```

El timeout se puede ajustar con:

```bash
GRPC_TIMEOUT_MS=5000 npm run listar
```

## Pruebas de interoperabilidad en Docker

Desde la raíz del proyecto, ejecuta el compose dedicado:

```bash
docker compose -f docker-compose.grpc-client.test.yaml up \
  --build \
  --abort-on-container-exit \
  --exit-code-from cliente-node-tests
```

El flujo levanta PostgreSQL, espera a que el servidor gRPC Python esté
saludable y ejecuta el cliente Node.js dentro de otro contenedor. Las pruebas
verifican el RPC server-streaming `ListarEquipos` y el manejo del estado
`NOT_FOUND` de `ConsultarEquipo`.

Para eliminar los contenedores y la red al finalizar:

```bash
docker compose -f docker-compose.grpc-client.test.yaml down -v
```
