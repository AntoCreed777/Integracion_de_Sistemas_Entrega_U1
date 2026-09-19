from generated import equipos_pb2, equipos_pb2_grpc


def test_consultar_equipo(grpc_channel, crear_equipo):
    stub = equipos_pb2_grpc.ServicioEquiposStub(grpc_channel)
    equipo = crear_equipo(
        equipo_id=1,
        nombre="Notebook",
        descripcion="Notebook Lenovo",
        cantidad_total=10,
        unidades_disponibles=5,
        activo=True
    )

    response = stub.ConsultarEquipo(equipos_pb2.EquipoRequest(id=equipo.equipo_id))

    assert response.id == equipo.id
    assert response.nombre == equipo.nombre
    assert response.descripcion == equipo.descripcion
    assert response.unidades_disponibles == equipo.unidades_disponibles
