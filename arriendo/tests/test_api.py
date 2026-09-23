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
