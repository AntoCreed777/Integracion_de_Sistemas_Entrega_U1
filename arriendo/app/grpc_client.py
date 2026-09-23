import os
import grpc
from fastapi import HTTPException, status

# Importamos los archivos generados en tiempo de construcción por el Dockerfile
from app.generated import equipos_pb2, equipos_pb2_grpc

GRPC_URL = os.getenv("EQUIPOS_GRPC_URL", "equipos-api:50051")

def get_grpc_stub():
    channel = grpc.insecure_channel(GRPC_URL)
    return equipos_pb2_grpc.ServicioEquiposStub(channel), channel

def reservar_unidad(equipment_id: int):
    stub, channel = get_grpc_stub()
    request = equipos_pb2.EquipoRequest(id=equipment_id)
    
    try:
        # 1. Consultar disponibilidad al servicio de Equipos
        disponibilidad = stub.ConsultarDisponibilidadEquipo(request)
        
        if disponibilidad.unidades_disponibles <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "INSUFFICIENT_STOCK", "message": f"El equipo {equipment_id} no tiene unidades disponibles."}
            )
            
        # 2. Ejecutar la reserva descontando el stock
        stub.ReservarEquipo(request)
        
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "EQUIPMENT_NOT_FOUND", "message": f"El equipo {equipment_id} no existe en el catálogo."}
            )
        elif e.code() == grpc.StatusCode.UNAVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "EQUIPMENTS_SERVICE_UNAVAILABLE", "message": "El servicio de Equipos no está disponible."}
            )
        elif e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={"code": "EQUIPMENTS_SERVICE_TIMEOUT", "message": "Timeout al conectar con Equipos."}
            )
        raise
    finally:
        channel.close()

def liberar_unidad(equipment_id: int):
    stub, channel = get_grpc_stub()
    request = equipos_pb2.EquipoRequest(id=equipment_id)
    
    try:
        stub.LiberarEquipo(request)
    except grpc.RpcError as e:
        if e.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "EQUIPMENTS_SERVICE_UNAVAILABLE", "message": "No se pudo comunicar con Equipos para liberar la unidad."}
            )
        raise
    finally:
        channel.close()