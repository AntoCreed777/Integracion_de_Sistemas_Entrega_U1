"""Prueba de integración: HTTP y gRPC reales, sin sustituir Equipos."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

import grpc
import pytest

from app.generated import equipos_pb2, equipos_pb2_grpc


pytestmark = pytest.mark.skipif(
    os.getenv("REAL_GRPC_TEST") != "1",
    reason="Requiere docker-compose.concurrent-integration.yaml",
)


def request_json(api_url, method, path, headers, payload=None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{api_url}{path}",
        data=body,
        headers={**headers, "Content-Type": "application/json"},
        method=method,
    )
    try:
        response = urlopen(request, timeout=10)
    except HTTPError as error:
        response = error

    with response:
        return response.status, json.load(response)


def test_dos_reservas_reales_de_la_ultima_unidad_terminan_en_409():
    grpc_url = os.environ["EQUIPOS_GRPC_URL"]
    api_url = os.environ["API_BASE_URL"]
    equipment = equipos_pb2.EquipoRequest(id=1)

    with grpc.insecure_channel(grpc_url) as channel:
        stub = equipos_pb2_grpc.ServicioEquiposStub(channel)

        # Deja una unidad para que la prueba pueda repetirse en el mismo entorno.
        available = stub.ConsultarDisponibilidadEquipo(equipment, timeout=5).unidades_disponibles
        if available == 0:
            stub.LiberarEquipo(equipment, timeout=5)
        else:
            for _ in range(available - 1):
                stub.ReservarEquipo(equipment, timeout=5)

        assert stub.ConsultarDisponibilidadEquipo(equipment, timeout=5).unidades_disponibles == 1

        # Comprueba que Equipos mismo acepta solo una reserva concurrente.
        grpc_start = Barrier(2)

        def reserve_via_grpc(_):
            grpc_start.wait(timeout=10)
            with grpc.insecure_channel(grpc_url) as worker_channel:
                worker_stub = equipos_pb2_grpc.ServicioEquiposStub(worker_channel)
                try:
                    worker_stub.ReservarEquipo(equipment, timeout=5)
                    return grpc.StatusCode.OK
                except grpc.RpcError as error:
                    return error.code()

        with ThreadPoolExecutor(max_workers=2) as pool:
            grpc_results = list(pool.map(reserve_via_grpc, range(2)))

        assert grpc_results.count(grpc.StatusCode.OK) == 1
        assert grpc_results.count(grpc.StatusCode.FAILED_PRECONDITION) == 1
        assert stub.ConsultarDisponibilidadEquipo(equipment, timeout=5).unidades_disponibles == 0

        # Repone la última unidad y ahora verifica el recorrido HTTP → gRPC → BD.
        stub.LiberarEquipo(equipment, timeout=5)

        headers = {"API-Key": "apikey_admin"}
        created_status, created = request_json(
            api_url,
            "POST",
            "/v1/clients",
            headers,
            {"name": "Cliente concurrente", "email": f"test-{uuid4()}@example.com"},
        )
        assert created_status == 201, created
        client_id = created["id"]

        http_start = Barrier(2)

        def reserve_via_http(_):
            http_start.wait(timeout=10)
            return request_json(
                api_url,
                "POST",
                "/v1/rentals",
                headers,
                {
                    "clientId": client_id,
                    "equipmentId": 1,
                    "startDate": "2026-09-20T10:00:00Z",
                    "endDate": "2026-09-25T18:00:00Z",
                },
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(reserve_via_http, range(2)))

        assert sorted(status for status, _ in responses) == [201, 409], responses
        conflict = next(body for status, body in responses if status == 409)
        assert conflict["code"] in {
            "INSUFFICIENT_STOCK",
            "INVALID_STATE_TRANSITION",
        }
        assert stub.ConsultarDisponibilidadEquipo(equipment, timeout=5).unidades_disponibles == 0

        history_status, history = request_json(
            api_url, "GET", f"/v1/clients/{client_id}", headers
        )
        assert history_status == 200, history
        assert len(history["rentalHistory"]["active"]) == 1
