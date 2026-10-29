# Cliente gRPC en Node.js

Este cliente demuestra interoperabilidad entre Node.js y el servicio gRPC de
Equipos implementado en Python. Carga directamente el archivo
[`../Equipos/equipos.proto`](../Equipos/equipos.proto), por lo que no necesita
código generado manualmente.

## 1. Ejecución local

### Requisitos

- Node.js 18+.
- El archivo `Equipos/equipos.proto`, incluido en el repositorio.
- Un servicio gRPC de Equipos accesible desde el host.

### Instalación

Desde la raíz del repositorio:

```bash
cd cliente-node
npm install
```

### Uso

Desde la carpeta `cliente-node`, configura la dirección del servicio y ejecuta
una operación:

```bash
EQUIPOS_GRPC_URL=localhost:50051 npm run consultar -- 1
EQUIPOS_GRPC_URL=localhost:50051 npm run disponibilidad -- 1
EQUIPOS_GRPC_URL=localhost:50051 npm run listar
EQUIPOS_GRPC_URL=localhost:50051 npm run reservar -- 1
EQUIPOS_GRPC_URL=localhost:50051 npm run liberar -- 1
EQUIPOS_GRPC_URL=localhost:50051 npm run demo -- 1
```

El comando solo funcionará si algún entorno publica el puerto gRPC en
`localhost:50051`. También puedes configurar otra dirección:

```bash
EQUIPOS_GRPC_URL=host:puerto npm run demo -- 1
```

El timeout se puede ajustar con:

```bash
GRPC_TIMEOUT_MS=5000 npm run listar
```

## 2. Ejecución en Docker

El Compose principal mantiene gRPC dentro de la red interna y no publica el
puerto `50051` en el host. Para ejecutar el cliente Node.js en Docker utiliza
el Compose dedicado de interoperabilidad.

Desde la raíz del repositorio:

```bash
docker compose -f docker-compose.grpc-client.test.yaml up \
  --build \
  --abort-on-container-exit \
  --exit-code-from cliente-node-tests
```

Este Compose:

1. Levanta PostgreSQL para Equipos.
2. Levanta el servicio gRPC de Equipos.
3. Espera a que el servicio gRPC esté saludable.
4. Construye el contenedor del cliente Node.js.
5. Ejecuta las pruebas de interoperabilidad dentro de Docker.

Las pruebas verifican el RPC server-streaming `ListarEquipos` y el manejo del
estado `NOT_FOUND` de `ConsultarEquipo`. El Dockerfile copia automáticamente
`Equipos/equipos.proto` dentro de la imagen del cliente.

Para eliminar los contenedores y la red al finalizar:

```bash
docker compose -f docker-compose.grpc-client.test.yaml down -v
```
