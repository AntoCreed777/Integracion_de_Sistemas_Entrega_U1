import os

import grpc
from fastapi import HTTPException, status

# Archivos generados durante la construcción de la imagen.
from app.generated import equipos_pb2, equipos_pb2_grpc


GRPC_URL = os.getenv("EQUIPOS_GRPC_URL", "equipos-api:50051")

GRPC_TIMEOUT_SECONDS = float(
    os.getenv("GRPC_TIMEOUT_SECONDS", "3")
)

if GRPC_TIMEOUT_SECONDS <= 0:
    raise ValueError(
        "GRPC_TIMEOUT_SECONDS debe ser mayor que cero"
    )


def get_grpc_stub():
    channel = grpc.insecure_channel(GRPC_URL)

    stub = equipos_pb2_grpc.ServicioEquiposStub(channel)

    return stub, channel


def reservar_unidad(equipment_id: int):
    stub, channel = get_grpc_stub()
    request = equipos_pb2.EquipoRequest(id=equipment_id)

    try:
        disponibilidad = stub.ConsultarDisponibilidadEquipo(
            request,
            timeout=GRPC_TIMEOUT_SECONDS,
        )

        if disponibilidad.unidades_disponibles <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "INSUFFICIENT_STOCK",
                    "message": (
                        f"El equipo {equipment_id} "
                        "no tiene unidades disponibles."
                    ),
                },
            )

        stub.ReservarEquipo(
            request,
            timeout=GRPC_TIMEOUT_SECONDS,
        )

    except grpc.RpcError as error:
        if error.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "EQUIPMENT_NOT_FOUND",
                    "message": (
                        f"El equipo {equipment_id} "
                        "no existe en el catálogo."
                    ),
                },
            ) from error

        if error.code() == grpc.StatusCode.UNAVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "EQUIPMENTS_SERVICE_UNAVAILABLE",
                    "message": (
                        "El servicio de Equipos "
                        "no está disponible."
                    ),
                },
            ) from error

        if error.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={
                    "code": "EQUIPMENTS_SERVICE_TIMEOUT",
                    "message": (
                        "Equipos no respondió dentro "
                        "del tiempo permitido."
                    ),
                },
            ) from error

        raise

    finally:
        channel.close()


def liberar_unidad(equipment_id: int):
    stub, channel = get_grpc_stub()
    request = equipos_pb2.EquipoRequest(id=equipment_id)

    try:
        stub.LiberarEquipo(
            request,
            timeout=GRPC_TIMEOUT_SECONDS,
        )

    except grpc.RpcError as error:
        if error.code() == grpc.StatusCode.UNAVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "EQUIPMENTS_SERVICE_UNAVAILABLE",
                    "message": (
                        "El servicio de Equipos "
                        "no está disponible."
                    ),
                },
            ) from error

        if error.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={
                    "code": "EQUIPMENTS_SERVICE_TIMEOUT",
                    "message": (
                        "Equipos no respondió dentro "
                        "del tiempo permitido."
                    ),
                },
            ) from error

        raise

    finally:
        channel.close()