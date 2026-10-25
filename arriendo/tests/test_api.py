from fastapi import HTTPException

CLIENTE = {"name": "Ana Pérez", "email": "ana@example.com"}
ARRIENDO = {
    "clientId": 1,
    "equipmentId": 50,
    "startDate": "2026-09-20T10:00:00Z",
    "endDate": "2026-09-25T18:00:00Z",
}


class TestHealth:
    def test_health(self, client):
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestClients:
    def test_admin_puede_crear_cliente(self, admin_client):
        response = admin_client.post("/v1/clients", json=CLIENTE)

        assert response.status_code == 201

    def test_crear_cliente_sin_autenticacion(self, unauthenticated_client):
        response = unauthenticated_client.post("/v1/clients", json=CLIENTE)

        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHORIZED"

    def test_cliente_no_puede_crear_cliente(self, cliente_client):
        response = cliente_client.post("/v1/clients", json=CLIENTE)

        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"

    def test_crear_cliente(self, client):
        response = client.post("/v1/clients", json=CLIENTE)

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == CLIENTE["name"]
        assert body["email"] == CLIENTE["email"]
        assert body["rentalHistory"] == {
            "active": [],
            "completed": [],
            "cancelled": [],
        }

    def test_crear_cliente_con_email_duplicado(self, client):
        client.post("/v1/clients", json=CLIENTE)

        response = client.post("/v1/clients", json=CLIENTE)

        assert response.status_code == 409
        assert response.json()["code"] == "EMAIL_ALREADY_EXISTS"

    def test_crear_cliente_con_datos_invalidos(self, client):
        response = client.post(
            "/v1/clients",
            json={"name": "", "email": "correo-invalido"},
        )

        assert response.status_code == 400
        assert response.json()["code"] == "BAD_REQUEST"

    def test_listar_clientes(self, client):
        client.post("/v1/clients", json=CLIENTE)

        response = client.get("/v1/clients")

        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_obtener_cliente_inexistente(self, client):
        response = client.get("/v1/clients/99999")

        assert response.status_code == 404
        assert response.json()["code"] == "CLIENT_NOT_FOUND"


class TestRentals:
    def test_cliente_no_puede_crear_arriendo(self, admin_client, cliente_client):
        created_client = admin_client.post("/v1/clients", json=CLIENTE).json()

        response = cliente_client.post(
            "/v1/rentals",
            json={**ARRIENDO, "clientId": created_client["id"]},
        )

        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"

    def test_cliente_no_puede_cancelar_arriendo(
        self,
        admin_client,
        cliente_client,
    ):
        created_client = admin_client.post("/v1/clients", json=CLIENTE).json()
        created = admin_client.post(
            "/v1/rentals",
            json={**ARRIENDO, "clientId": created_client["id"]},
        ).json()

        response = cliente_client.post(f"/v1/rentals/{created['id']}/cancel")

        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"

    def test_crear_arriendo(self, client):
        created_client = client.post("/v1/clients", json=CLIENTE).json()

        response = client.post(
            "/v1/rentals",
            json={**ARRIENDO, "clientId": created_client["id"]},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["clientId"] == created_client["id"]
        assert body["equipmentId"] == ARRIENDO["equipmentId"]
        assert body["status"] == "ACTIVE"

    def test_crear_arriendo_con_cliente_inexistente(self, client):
        response = client.post("/v1/rentals", json=ARRIENDO)

        assert response.status_code == 404
        assert response.json()["code"] == "CLIENT_NOT_FOUND"

    def test_crear_arriendo_con_datos_invalidos(self, client):
        response = client.post(
            "/v1/rentals",
            json={**ARRIENDO, "clientId": 0},
        )

        assert response.status_code == 400
        assert response.json()["code"] == "BAD_REQUEST"

    def test_listar_y_obtener_arriendo(self, client):
        created_client = client.post("/v1/clients", json=CLIENTE).json()
        created = client.post(
            "/v1/rentals",
            json={**ARRIENDO, "clientId": created_client["id"]},
        ).json()

        listed = client.get("/v1/rentals")
        retrieved = client.get(f"/v1/rentals/{created['id']}")

        assert listed.status_code == 200
        assert len(listed.json()) == 1
        assert retrieved.status_code == 200
        assert retrieved.json()["id"] == created["id"]

    def test_cache_se_inyecta_en_el_router(self, client):
        from app.main import app
        from app.redis import get_rental_cache

        class InMemoryRentalCache:
            enabled = True

            def __init__(self):
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def set(self, key, value, ttl_seconds=60):
                self.values[key] = value

            def invalidate(self, rental_id=None):
                self.values.clear()

        cache = InMemoryRentalCache()
        app.dependency_overrides[get_rental_cache] = lambda: cache
        created_client = client.post("/v1/clients", json=CLIENTE).json()
        client.post(
            "/v1/rentals",
            json={**ARRIENDO, "clientId": created_client["id"]},
        )

        first_response = client.get("/v1/rentals")
        second_response = client.get("/v1/rentals")

        assert first_response.headers["CACHE_STATUS"] == "MISS"
        assert second_response.headers["CACHE_STATUS"] == "HIT"
        assert first_response.json() == second_response.json()

    def test_obtener_arriendo_inexistente(self, client):
        response = client.get("/v1/rentals/99999")

        assert response.status_code == 404
        assert response.json()["code"] == "RENTAL_NOT_FOUND"

    def test_cancelar_arriendo(self, client):
        created_client = client.post("/v1/clients", json=CLIENTE).json()
        created = client.post(
            "/v1/rentals",
            json={**ARRIENDO, "clientId": created_client["id"]},
        ).json()

        response = client.post(f"/v1/rentals/{created['id']}/cancel")

        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"

    def test_error_al_liberar_conserva_arriendo_activo(
        self,
        client,
        db_session,
        crear_arriendo,
        monkeypatch,
    ):
        from app.routers.v1 import rentals

        rental = crear_arriendo()

        def fail_to_release(equipment_id):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "INVALID_STATE_TRANSITION",
                    "message": "No se pudo liberar la unidad.",
                },
            )

        monkeypatch.setattr(rentals, "liberar_unidad", fail_to_release)

        response = client.post(f"/v1/rentals/{rental.id}/cancel")

        db_session.refresh(rental)
        assert response.status_code == 409
        assert rental.status == "ACTIVE"

    def test_retorno_completa_arriendo(self, client):
        created_client = client.post("/v1/clients", json=CLIENTE).json()
        created = client.post(
            "/v1/rentals",
            json={**ARRIENDO, "clientId": created_client["id"]},
        ).json()

        response = client.post(f"/v1/rentals/{created['id']}/return")

        assert response.status_code == 200
        assert response.json()["status"] == "COMPLETED"

    def test_no_se_puede_cancelar_arriendo_cancelado(self, client):
        created_client = client.post("/v1/clients", json=CLIENTE).json()
        created = client.post(
            "/v1/rentals",
            json={**ARRIENDO, "clientId": created_client["id"]},
        ).json()
        client.post(f"/v1/rentals/{created['id']}/cancel")

        response = client.post(f"/v1/rentals/{created['id']}/cancel")

        assert response.status_code == 409
        assert response.json()["code"] == "INVALID_STATE_TRANSITION"

    def test_historial_cliente_se_actualiza(self, client):
        created_client = client.post("/v1/clients", json=CLIENTE).json()
        created = client.post(
            "/v1/rentals",
            json={**ARRIENDO, "clientId": created_client["id"]},
        ).json()
        client.post(f"/v1/rentals/{created['id']}/return")

        response = client.get(f"/v1/clients/{created_client['id']}")

        assert response.status_code == 200
        assert response.json()["rentalHistory"] == {
            "active": [],
            "completed": [created["id"]],
            "cancelled": [],
        }
