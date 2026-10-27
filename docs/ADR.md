# Architecture Decision Records (ADRs)

**ADR-001 - Estilo de integración y descomposición. Implementación de microservicios por sobre un monolito.**

**Estado:** Aceptada

**Contexto.** El sistema gestiona equipos de arriendo y el ciclo de vida de los arriendos. Ambas responsabilidades podrían vivir en un único servicio monolítico con una sola base de datos, en dos servicios que compartan base de datos, o en dos servicios independientes con datos propios que se comunican por gRPC, como está implementado actualmente. La decisión es necesaria porque el servicio de Equipos puede ser reutilizado por otros consumidores además de Arriendos, y porque el flujo de arriendos no debería depender del ciclo de cambios del inventario.

**Alternativas consideradas.**
* *Opción A* -- Integrar todo como un gran monolito, con una única base de datos. Permite transacciones ACID entre reserva y arriendo, evita replicación de datos innecesaria y plantea una arquitectura más simple. Cuesta acoplar los ciclos de vida, el escalamiento y los fallos de ambos dominios.
* *Opción B* -- Monolito modular (un solo despliegue, módulos con límites internos). Separa la lógica sin perder transacciones. Cuesta que los límites se sostienen solo por disciplina del equipo y que sigue habiendo un único proceso que escalar y que puede caer.
* *Opción C* -- Dos servicios con base de datos compartida. Permite desplegar por separado, mantener la transacción local y una llave foránea real sobre `equipment_id`. Cuesta que el esquema se convierte en un contrato implícito y que ambos servicios pueden escribir las mismas tablas.
* *Opción D* -- Integrar todo separado en dos microservicios, con una base de datos propia de cada uno. Mejora la separación de la lógica de negocio, da propiedad exclusiva de los datos y permite un mejor desarrollo en paralelo. Cuesta perder la transacción entre ambos servicios y la llave foránea real sobre `equipment_id`.

**Decisión.** Se eligió separar en dos microservicios, uno para el manejo de los arriendos y otro para el manejo de los equipos, cada uno dueño exclusivo de su base de datos y comunicados por gRPC (`reservar_unidad` y `liberar_unidad`) para el arriendo y la liberación de equipos.

**Justificación.** La frontera entre servicios sigue la responsabilidad y la propiedad de los datos: Equipos es dueño de la existencia, los atributos y la disponibilidad de cada unidad, y Arriendos es dueño de los clientes, los arriendos y su ciclo de vida (`ACTIVE`, `COMPLETED`, `CANCELLED`). Cada dato tiene un único servicio que puede escribirlo, y el otro solo lo referencia o lo consulta por API. El criterio es quién escribe el dato, no quién lo consulta más: que Arriendos pregunte seguido por disponibilidad no justifica mover la disponibilidad a Arriendos, porque eso crearía dos fuentes de verdad.

Se descarta el monolito (Opciones A y B) por tres razones:
* **Ciclos de vida distintos.** El inventario cambia por razones de mantenimiento, altas y bajas; los arriendos cambian por reglas comerciales. En un monolito, cada cambio de uno obliga a desplegar y regresionar el otro.
* **Escalamiento independiente.** Si el servicio de Equipos recibe un aumento de consultas, puede escalarse sin escalar todo el servicio de Arriendos, y un pico de creación de arriendos no obliga a escalar el inventario. Un monolito, incluso modular, tiene un único proceso y un único pool de recursos.
* **Reutilización de Equipos.** El servicio de Equipos puede ser usado por otros servicios además de Arriendos. Mantenerlo independiente permite reutilizarlo sin acoplar directamente su lógica al sistema de arriendos.

Se descarta la base de datos compartida (Opción C) porque rompe la propiedad de los datos: si Arriendos puede escribir la tabla de unidades, la disponibilidad deja de tener un único dueño y puede modificarse sin pasar por las reglas de Equipos. Además, el esquema pasa a ser el contrato entre servicios y no tiene versionado: cualquier cambio de columna puede romper al otro servicio sin aviso, lo que deja un monolito distribuido (dos procesos acoplados como uno). Por último, una base de datos compartida es un punto único de falla y de saturación para ambos servicios, justamente lo que la separación busca evitar.

Se aceptan dos duplicaciones de datos a propósito:
* `equipment_id` **en** `Rental`**.** Arriendos guarda la referencia a la unidad arrendada para mostrar y gestionar el arriendo sin consultar a Equipos en cada lectura. Es una referencia, no una copia del equipo.
* **Copia de los arriendos en Redis** (`rental:{id}` y `rentals:list:*`, con TTL de 60 s). Reduce la carga de la base de datos en las lecturas más frecuentes. La coherencia se mantiene invalidando la clave puntual y todas las claves de listado en cada mutación (`create_rental`, `cancel_rental`, `return_rental`).

[azure-microservices-data]

**Costo aceptado.** Se aceptan los siguientes costos:
* **Dependencia de comunicación.** Cuando Arriendos necesita información o una acción de Equipos, debe consultar a ese servicio, lo que agrega latencia y puede provocar errores si Equipos no está disponible.
* **Pérdida de atomicidad.** Si `reservar_unidad` tiene éxito pero el `commit` local falla, la compensación (`liberar_unidad`) puede fallar también y dejar una unidad reservada sin arriendo asociado. Se acepta este riesgo, documentado en el código, a cambio de no implementar una transacción distribuida.
* `equipment_id` **no validable fuera de la reserva.** Sin llave foránea real entre servicios, Arriendos solo comprueba que la unidad existe en el instante de `reservar_unidad`. Si después una unidad se elimina o cambia en Equipos, los arriendos que la referencian quedan con un `equipment_id` colgante, y Arriendos no se entera. En el código actual, `cancel_rental` y `return_rental` llaman a `liberar_unidad` antes de cambiar el estado local, por lo que un arriendo podría quedar `ACTIVE` indefinidamente si Equipos rechaza la liberación. Se propone mitigarlo con tres medidas: Equipos no elimina físicamente unidades ni reutiliza IDs (baja lógica), `liberar_unidad` es idempotente, y un proceso periódico de reconciliación compara las reservas de Equipos con los arriendos `ACTIVE`.
* **Obsolescencia en Redis.** Los datos pueden estar desfasados hasta 60 s, y cada endpoint nuevo que modifique `Rental` debe acordarse de invalidar las claves correspondientes, sin que ningún error avise si se olvida.

**Consecuencias.** Se introduce comunicación entre servicios, lo que agrega latencia, posibles fallos de red y mayor complejidad operacional en comparación con un monolito. La consistencia entre ambos servicios pasa a ser responsabilidad de la aplicación (compensación, reglas de baja y reconciliación) y no de la base de datos. Esta decisión habría que revisarla si las reservas huérfanas o los arriendos imposibles de cerrar dejan de ser casos raros (convendría una saga formal o eventos), o si el equipo y el tráfico son tan pequeños que operar dos servicios cuesta más de lo que aporta (la Opción B sería entonces la alternativa razonable).

---

**ADR-002 - REST frente a gRPC. REST como cara pública y gRPC como contacto para la conexión.**

**Estado:** Aceptada

**Contexto.** Una vez elegido la arquitectura de microservicios, se busca implementar un método de comunicación entre servicios y una forma de interactuar con el entorno.

**Alternativas consideradas.** 
* *Opción A* -- Implementar websockets como protocolo de comunicación e implementar REST en ambos extremos.
* *Opción B* -- Implementar gRPC como protocolo de comunicación y REST como metodo de interacción con el usuario.

**Decisión.** Se eligió implementar el protocolo gRPC como metodo de comunicación y usar REST como método de interacción con el usuario.

**Justificación.** El punto que descarta WebSockets es el tipo de interacción: `reservar_unidad` necesita una confirmación explícita e inmediata (¿se reservó o no?) antes de que `create_rental` pueda seguir — es RPC, no un flujo de eventos asíncronos. gRPC modela esto de forma nativa: la llamada devuelve una respuesta tipada o lanza un error, con timeouts y códigos de estado estandarizados. WebSockets, en cambio, es un canal de mensajes sin una noción incorporada de "esta respuesta contesta a esa solicitud" ni de tipado — tendríamos que reinventar sobre JSON crudo un protocolo de correlación de mensajes, control de errores y timeouts que gRPC ya trae resuelto, y encima sin el tipado en compilación que si aporta `.proto`. A eso se suma que gRPC corre sobre HTTP/2 con multiplexado, entregando el payload compacto de Protobuf sin el overhead de mantener una conexión persistente abierta expresamente para esto. WebSockets solo se justificaría si Equipos necesitara notificar a Arriendos de cambios que Arriendos no inició (por ejemplo, una unidad dada de baja por mantenimiento) — un caso que hoy no existe en el flujo descrito. [grpc-docs]

**Costo aceptado.** Se manda todo el patrón interno por request-response síncrono vía gRPC, sacrificando la posibilidad de que Equipos notifique proactivamente a Arriendos de cambios de estado que no fueron iniciados por una llamada de Arriendos. Si ese caso de uso aparece en el futuro, hoy no hay canal para resolverlo sin agregar algo nuevo.

**Consecuencias.** Mientras la relación entre ambos servicios se mantenga como solicitud-respuesta (reservar/liberar), gRPC sigue siendo la opción correcta y no hay necesidad de introducir infraestructura de conexiones persistentes. Si en el futuro el negocio necesita que Equipos empuje eventos a Arriendos (o a otros consumidores) sin que estos pregunten, esta decisión debería revisarse: ahí sí valdría la pena evaluar WebSockets o, más probablemente, un mecanismo de streaming (gRPC server-streaming o un message broker) en vez de forzar ese patrón sobre el RPC síncrono actual.

---

**ADR-003 - Contrato, versionado y evolución. Evolución de la API y cambios en los contratos.**

**Estado:** Propuesta

**Contexto.** El sistema ya expone contratos explícitos en ambos bordes: modelos Pydantic/OpenAPI en la API pública (`ClientRequest`, `RentalResponse`, etc.) y definiciones `.proto` en la comunicación interna con Catálogo. Ambos contratos van a cambiar con el tiempo —nuevos campos, nuevos estados, nuevas reglas de negocio— y hay consumidores externos que no se despliegan al mismo tiempo que este servicio. Hace falta una regla explícita de qué cambios son seguros y cómo se comunican los que no lo son, o cada cambio de contrato se convierte en una negociación adhoc.

**Alternativas consideradas.** 
* *Opción A* -- Versionado en la URI (`/v1/...`, `/v2/...`), rompiendo compatibilidad solo al cambiar de versión.
* *Opción B* -- Un solo `/v1/` para siempre, evolucionando el contrato solo con cambios aditivos (nunca se rompe nada, nunca se versiona).

**Decisión.** Versionado explícito en la URI (`/v1/...`), donde el prefijo de versión solo sube cuando hay un cambio incompatible; los cambios compatibles se agregan dentro de la misma versión. [protobuf-proto3]

**Justificación.** El código ya sigue esta convención (`prefix='/v1/clients'`, `prefix='/v1/rentals'`), así que la decisión formaliza lo existente en vez de introducir algo nuevo. Frente a la Opción B, forzar "todo compatible para siempre" no es sostenible: tarde o temprano una regla de negocio exige un cambio real de forma (ejemplo concreto más abajo), y sin una vía de versión nueva ese cambio se aplicaría sobre los mismos consumidores sin aviso, rompiendo integraciones en producción sin que lo noten hasta que fallan.

**Costo aceptado.** Mantener `/v1/` y una eventual `/v2/` corriendo en paralelo durante el período de migración implica duplicar parcialmente routers y lógica de traducción entre versiones (o al menos mantener ambos hasta deprecar la vieja), y coordinar con los consumidores un aviso de deprecación con plazo antes de apagar `/v1/`.

**Consecuencias.** Se logra establecer diferencias claras entre distintas versiones, y a la vez se permite tener varias versiones de la aplicación activas a la vez, de esta forma no se fuerza a los clientes a cambiarse y se puede tener mayor control sobre quienes usan que versión. Se va a requerir de adapatar los contratos al momento de cambiar de versión y de mantener la documentación y servidores activos para las versiones activas generando un mayor uso de recursos, pero que se puede eliminar una vez se cambien definitivamente de versión. Esta decisión queda como propuesta ya que se tendrá que hacer valida a medida que se vayan desarrollando estas nuevas versiones de la aplicación.

---

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