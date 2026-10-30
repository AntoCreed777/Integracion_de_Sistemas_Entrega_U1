
**ADR-004 - Resiliencia ante fallas. Uso de timesout y respuestas HTTP.**

**Estado:** Aceptado

**Contexto.** Algunas llamadas de la API de Arriendos requieren operaciones del servicio de Equipos y, por lo tanto, dependen de una comunicación estable entre microservicios. Se necesita limitar cuánto espera Arriendos y definir una respuesta REST para cada tipo de falla de gRPC.

**Alternativas consideradas.** 
* *Opción A* -- Sin timeout explícito ofrece una implementación mínima, cero código adicional pero basta con que una sola instancia lenta de Equipos para dejar conexiones de Arriendos esperando.
* *Opción B* -- Timeout explícito y corto en la llamada gRPC, con fail-fast hacia el cliente ofrece que no se queden llamadas en espera indefinida, sino que se cortan y entregan una respuesta acorde a las métricas expuestas en los contratos.
* *Opción C* -- Servir datos de caché como fallback cuando Equipo no responde puede ayudar a agilizar las consultas de llamado, pero no permite que se usen consultas del tipo POST, ya que el cache no asegura que los datos se mantengan íntegros o se respete lo que hay en la base de datos.

**Decisión.** Timeout explícito y corto en la llamada gRPC, con fail-fast hacia el cliente, reaccionando con un código de error preestablecido por el contrato OPENAPI, manteniendo la integridad segura y evitando tiempos de espera eternos. [grpc-deadlines]

**Justificación.** Las operaciones de escritura requieren confirmar el resultado en Equipos; una respuesta cacheada no puede confirmar ni realizar una reserva o liberación, por lo que se descarta la opción C para estas operaciones. También se descarta la opción A: sin un límite, solicitudes lentas podrían acumularse y mantener recursos ocupados indefinidamente. Los errores se diferencian por su causa: una conexión rechazada rápidamente se traduce a HTTP 503 (`UNAVAILABLE`), mientras que una operación que no responde antes del deadline se traduce a HTTP 504 (`DEADLINE_EXCEEDED`).

A su vez, tener códigos diferenciados para cada falla posible le da al consumidor información adicional del error y permite actuar en consecuencia. Tener estas respuestas declaradas entrega el fallo y las maneras de proceder.

**Costo aceptado.** Con fail-fast, se rechazan operaciones que quizás habrían tenido éxito si Arriendos hubiera esperado un par de segundos más — se sacrifica disponibilidad "optimista" por previsibilidad y por proteger la capacidad del propio servicio. Además, un timeout mal calibrado (demasiado corto) puede generar falsos 504 bajo carga normal de Equipos si su latencia p99 se acerca al valor elegido; el valor del timeout debe fijarse con datos reales de latencia de Equipos, no arbitrariamente.

**Método y resultado observado.** Se utilizó el script `experimentación_resiliencia/test_resiliencia.py` con Arriendos y Equipos levantados en Docker, un cliente y un equipo de prueba existentes y una solicitud válida `POST /v1/rentals`. Para simular una dependencia lenta, el script pausa el contenedor `equipos-api` con `docker pause`, mide el tiempo de respuesta y compara el estado HTTP recibido con el timeout configurado (`GRPC_TIMEOUT_SECONDS = 3`). En la evaluación, esta solicitud devolvió HTTP 504 (`DEADLINE_EXCEEDED`), no 503. El resultado es coherente con el escenario: Equipos seguía en ejecución, pero no respondía mientras estaba pausado, por lo que gRPC agotó el deadline. En cambio, cuando se reemplaza Equipos por un contenedor sin servicio y la conexión se rechaza inmediatamente, corresponde HTTP 503 (`UNAVAILABLE`). Son fallas distintas y el código HTTP depende de cuál se produzca.

**Consecuencias.** Los endpoints `create_rental`, `cancel_rental` y `return_rental` deben aplicar un timeout explícito y traducir los errores gRPC: `DEADLINE_EXCEEDED` a HTTP 504 y `UNAVAILABLE` a HTTP 503, en lugar de devolver un 500 genérico. Si en el futuro los fallos de Equipos bajo carga son frecuentes, habría que evaluar un circuit breaker para dejar de enviar solicitudes temporalmente a una dependencia degradada. [grpc-deadlines, rfc9110]