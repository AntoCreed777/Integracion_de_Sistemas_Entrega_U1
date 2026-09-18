import os
from concurrent import futures

import grpc

from app.servicio_equipos import ServicioEquipos
from generated import equipos_pb2_grpc

from app.init_db import crear_tablas


def obtener_puerto_grpc() -> int:
    valor = os.getenv("GRPC_PORT", "50051")

    try:
        puerto = int(valor)
    except ValueError as error:
        raise ValueError("GRPC_PORT debe ser un numero entero") from error

    if not 1 <= puerto <= 65535:
        raise ValueError("GRPC_PORT debe estar entre 1 y 65535")

    return puerto


def crear_servidor(direccion: str) -> grpc.Server:
    servidor = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
    )

    equipos_pb2_grpc.add_ServicioEquiposServicer_to_server(
        ServicioEquipos(),
        servidor,
    )

    puerto_asignado = servidor.add_insecure_port(direccion)
    if puerto_asignado == 0:
        raise RuntimeError(f"No se pudo escuchar en {direccion}")

    return servidor


def main() -> None:
    host = os.getenv("GRPC_HOST", "[::]")
    puerto = obtener_puerto_grpc()
    direccion = f"{host}:{puerto}"

    crear_tablas()
    

    servidor = crear_servidor(direccion)
    servidor.start()

    print(f"Servidor gRPC de Equipos escuchando en {direccion}")

    try:
        servidor.wait_for_termination()
    except KeyboardInterrupt:
        print("Deteniendo servidor gRPC")
        servidor.stop(grace=5)


if __name__ == "__main__":
    main()
