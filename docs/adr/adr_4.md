
**ADR-004 - Resiliencia ante fallas. Uso de timesout y respuestas HTTP.**

**Estado:** Aceptado

**Contexto.** Algunos de las llamadas de la API de Arriendo requieren de utilidades de la API de Equipo, pero para que estas llamadas se resuelvan de manera exitosa se requiere de una conexión estable entre microservicios. Para esto se requeiere evaluar los metodos de control y de timesout que se ocuparan para manejar estos casos de error.

**Alternativas consideradas.** 
* *Opción A* -- Sin timeout explícito ofrece una implementación mínima, cero código adicional pero basta con que una sola instancia lenta de Equipos para dejar conexiones de Arriendos esperando.
* *Opción B* -- Timeout explícito y corto en la llamada gRPC, con fail-fast hacia el cliente ofrece que no se queden llamadas en espera indefinida, sino que se cortan y entregan una respuesta acorde a las métricas expuestas en los contratos.
* *Opción C* -- Servir datos de caché como fallback cuando Equipo no responde puede ayudar a agilizar las consultas de llamado, pero no permite que se usen consultas del tipo POST, ya que el cache no asegura que los datos se mantengan íntegros o se respete lo que hay en la base de datos.

**Decisión.** Timeout explícito y corto en la llamada gRPC, con fail-fast hacia el cliente, reaccionando con un código de error preestablecido por el contrato OPENAPI, manteniendo la integridad segura y evitando tiempos de espera eternos. [grpc-deadlines]

**Justificación.** Dado que los endpoints de Arriendo requieren de escribir en la base de datos de Equipos, no es posible usar la cache como forma de resiliencia, ya que esta no asegura la escritura de los datos alterados en la base de datos de Equipo, por lo que al momento de actualizarse podrían haber fallas e incoherencias si es que hubieran dos o mas servicios conectados, de esta forma se descarta la opción C. Y la opción A queda claramente descartada, ya que si no hay un tiempo máximo para las peticiones, estas se acumularían en una cola que no sabe cuando va a volver a activarse el microservicio de Equipos, generando posibles incosistencias entre bases de datos y provocando demora y fallas a lo largo de la aplicación. 

A su vez, tener códigos diferenciados para cada falla posible le da al consumidor información adicional del error y permite actuar en consecuencia. Tener estas respuestas declaradas entrega el fallo y las maneras de proceder.

**Costo aceptado.** Con fail-fast, se rechazan operaciones que quizás habrían tenido éxito si Arriendos hubiera esperado un par de segundos más — se sacrifica disponibilidad "optimista" por previsibilidad y por proteger la capacidad del propio servicio. Además, un timeout mal calibrado (demasiado corto) puede generar falsos 504 bajo carga normal de Equipos si su latencia p99 se acerca al valor elegido; el valor del timeout debe fijarse con datos reales de latencia de Equipos, no arbitrariamente.

**Consecuencias.** Los endpoints `create_rental`, `cancel_rental` y `return_rental` deben envolver la llamada gRPC con un timeout explícito y traducir explícitamente las excepciones de gRPC (`DEADLINE_EXCEEDED` → 504, `UNAVAILABLE` → 503) en vez de dejar que una excepción no capturada llegue como 500 genérico. Si en el futuro el volumen de fallos de Catálogo bajo carga alta resulta frecuente, habría que revisar esta decisión e incorporar un circuit breaker (abrir el circuito tras N fallos consecutivos y devolver 503 inmediatamente sin ni siquiera intentar la llamada) para evitar seguir golpeando a un Equipos ya degradado. [grpc-deadlines, rfc9110]