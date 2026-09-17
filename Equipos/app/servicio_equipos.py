import grpc

from generated import equipos_pb2
from generated import equipos_pb2_grpc


class ServicioEquipos(equipos_pb2_grpc.ServicioEquiposServicer):
    """Implementacion pendiente del contrato definido en equipos.proto."""

    def ConsultarEquipo(self, request, context):
        # TODO: Buscar el equipo por request.id.
        context.abort(
            grpc.StatusCode.UNIMPLEMENTED,
            "ConsultarEquipo aun no ha sido implementado",
        )

    def ConsultarDisponibilidadEquipo(self, request, context):
        # TODO: Consultar las unidades disponibles del equipo.
        context.abort(
            grpc.StatusCode.UNIMPLEMENTED,
            "ConsultarDisponibilidadEquipo aun no ha sido implementado",
        )

    def ListarEquipos(self, request, context):
        # TODO: Obtener el catalogo y emitir cada equipo con yield.
        context.abort(
            grpc.StatusCode.UNIMPLEMENTED,
            "ListarEquipos aun no ha sido implementado",
        )

        # Mantiene este metodo como generador para el server streaming.
        yield equipos_pb2.Equipo()

    def ReservarEquipo(self, request, context):
        # TODO: Descontar una unidad de forma atomica.
        context.abort(
            grpc.StatusCode.UNIMPLEMENTED,
            "ReservarEquipo aun no ha sido implementado",
        )

    def LiberarEquipo(self, request, context):
        # TODO: Devolver una unidad sin superar el total disponible.
        context.abort(
            grpc.StatusCode.UNIMPLEMENTED,
            "LiberarEquipo aun no ha sido implementado",
        )
