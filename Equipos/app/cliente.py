import argparse
import os
import sys

import grpc
from google.protobuf import empty_pb2
from google.protobuf.json_format import MessageToJson

from generated import equipos_pb2
from generated import equipos_pb2_grpc


OPERACIONES_CON_ID = {
    "consultar": "ConsultarEquipo",
    "disponibilidad": "ConsultarDisponibilidadEquipo",
    "reservar": "ReservarEquipo",
    "liberar": "LiberarEquipo",
}


def crear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cliente de prueba para el microservicio Equipos",
    )
    parser.add_argument(
        "operacion",
        choices=[*OPERACIONES_CON_ID, "listar"],
        help="RPC que se desea probar",
    )
    parser.add_argument(
        "id",
        nargs="?",
        help="ID del equipo; no se utiliza al listar",
    )
    return parser.parse_args()


def imprimir_mensaje(mensaje) -> None:
    print(MessageToJson(mensaje, preserving_proto_field_name=True))


def ejecutar(stub, operacion: str, equipo_id: str | None) -> None:
    timeout = float(os.getenv("GRPC_CLIENT_TIMEOUT", "5"))

    if operacion == "listar":
        for equipo in stub.ListarEquipos(empty_pb2.Empty(), timeout=timeout):
            imprimir_mensaje(equipo)
        return

    if not equipo_id:
        raise ValueError(f"La operacion {operacion} necesita el ID de un equipo")

    solicitud = equipos_pb2.EquipoRequest(id=equipo_id)
    nombre_rpc = OPERACIONES_CON_ID[operacion]
    rpc = getattr(stub, nombre_rpc)
    respuesta = rpc(solicitud, timeout=timeout)
    imprimir_mensaje(respuesta)


def main() -> int:
    argumentos = crear_argumentos()
    host = os.getenv("GRPC_SERVER_HOST", "localhost")
    puerto = os.getenv("GRPC_SERVER_PORT", "50051")
    direccion = f"{host}:{puerto}"

    try:
        with grpc.insecure_channel(direccion) as canal:
            grpc.channel_ready_future(canal).result(timeout=5)
            stub = equipos_pb2_grpc.ServicioEquiposStub(canal)
            ejecutar(stub, argumentos.operacion, argumentos.id)
    except grpc.FutureTimeoutError:
        print(f"No fue posible conectarse con {direccion}", file=sys.stderr)
        return 1
    except grpc.RpcError as error:
        print(
            f"RPC finalizo con {error.code().name}: {error.details()}",
            file=sys.stderr,
        )
        return 1
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
