from enum import Enum, auto

class Scenario(Enum):
    A = auto()  # mismo recurso, sin Redis.
    B = auto()  # mismo recurso repetido; Redis debe estar precargado.
    C = auto()  # recursos distintos, que no deben estar previamente en Redis.
    D = auto()  # mitad de recursos precargados y mitad nuevos.
    ALL = auto()  # Ejecuta todos los escenarios.