import grpc
from app.database import SessionLocal
from app.models.equipo import Equipo, liberar_equipo, reservar_equipo
from generated import equipos_pb2, equipos_pb2_grpc
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
from google.protobuf import empty_pb2

class ServicioEquipos(equipos_pb2_grpc.ServicioEquiposServicer):
    """Implementacion del contrato definido en equipos.proto."""

    def ConsultarEquipo(self, request, context):
        db = SessionLocal()
        try:
            equipo = (
                db.query(Equipo)
                .filter(
                    Equipo.equipo_id == int(request.id),
                    Equipo.activo == True,
                )
                .one()
            )

            print("equipo:", equipo)
            print("equipo_id:", equipo.equipo_id, type(equipo.equipo_id))
            print("nombre:", equipo.nombre, type(equipo.nombre))
            print("descripcion:", equipo.descripcion, type(equipo.descripcion))
            print(
                "cantidad_disponible:",
                equipo.cantidad_disponible,
                type(equipo.cantidad_disponible),
            )

            response = equipos_pb2.Equipo(
                id=int(equipo.equipo_id),
                nombre=str(equipo.nombre),
                descripcion=str(equipo.descripcion),
                unidades_disponibles=int(equipo.cantidad_disponible),
            )

            return response

        except NoResultFound as e:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Equipo no encontrado: {str(e)}",
            )
        except MultipleResultsFound as e:
            context.abort(
                grpc.StatusCode.INTERNAL,
                f"Error (múltiples resultados): {str(e)}",
            )
        except Exception as e:

            context.abort(
                grpc.StatusCode.INTERNAL,
                f"Error al consultar equipo: {str(e)}",
            )
        finally:
            db.close()

    def ConsultarDisponibilidadEquipo(self, request, context):
        db = SessionLocal()
        try:
            equipo = (
                db.query(Equipo)
                .filter(Equipo.equipo_id == int(request.id), Equipo.activo == True)
                .one()
            )
            return equipos_pb2.EquipoDisponibilidad(
                id=equipo.equipo_id, unidades_disponibles=equipo.cantidad_disponible
            )
        except NoResultFound as e:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Equipo no encontrado: {str(e)}",
            )
        except MultipleResultsFound as e:
            context.abort(
                grpc.StatusCode.INTERNAL,
                f"Error (múltiples resultados): {str(e)}",
            )
        except Exception as e:
            context.abort(
                grpc.StatusCode.INTERNAL,
                f"Error al consultar disponibilidad: {str(e)}",
            )

        finally:
            db.close()

    def ListarEquipos(self, request, context):
        db = SessionLocal()
        # Deberiamos de colocar un limite de resultados y paginacion
        try:
            equipos = db.query(Equipo).filter(Equipo.activo == True).yield_per(100)

            for equipo in equipos:
                yield equipos_pb2.Equipo(
                    id=equipo.equipo_id,
                    nombre=equipo.nombre,
                    descripcion=equipo.descripcion,
                    unidades_disponibles=equipo.cantidad_disponible,
                )

        except Exception as e:
            context.abort(
                grpc.StatusCode.INTERNAL,
                f"Error al listar equipos: {str(e)}",
            )
        finally:
            db.close()

    def ReservarEquipo(self, request, context):
        db = SessionLocal()

        try:
            reservado = reservar_equipo(db, int(request.id))

        except Exception as e:
            context.abort(
                grpc.StatusCode.INTERNAL,
                f"Error al reservar equipo: {str(e)}",
            )
        finally:
            db.close()

        if not reservado:
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                "No se puede reservar el equipo",
            )

        return empty_pb2.Empty()

    def LiberarEquipo(self, request, context):
        db = SessionLocal()

        try:
            reservado = liberar_equipo(db, int(request.id))

        except Exception as e:
            context.abort(
                grpc.StatusCode.INTERNAL,
                f"Error al liberar equipo: {str(e)}",
            )
        finally:
            db.close()

        if not reservado:
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                "No se puede liberar el equipo",
            )

        return empty_pb2.Empty()
