from enum import Enum

class Scenario(Enum):
    A = "A"  # mismo recurso, sin Redis.
    B = "B"  # mismo recurso repetido; Redis debe estar precargado.
    C = "C"  # recursos distintos, que no deben estar previamente en Redis.
    D = "D"  # mitad de recursos precargados y mitad nuevos.
    ALL = "ALL"  # Ejecuta todos los escenarios.