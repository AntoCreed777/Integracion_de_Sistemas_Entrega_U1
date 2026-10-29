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
