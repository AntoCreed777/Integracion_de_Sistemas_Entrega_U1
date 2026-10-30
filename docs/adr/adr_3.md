**ADR-003 - Contrato, versionado y evolución. Evolución de la API y cambios en los contratos.**

**Estado:** Aceptado

**Contexto.** El sistema ya expone contratos explícitos en ambos bordes: modelos Pydantic/OpenAPI en la API pública (`ClientRequest`, `RentalResponse`, etc.) y definiciones `.proto` en la comunicación interna con Equipos. Ambos contratos pueden cambiar con el tiempo —nuevos campos, nuevos estados, nuevas reglas de negocio— y sus consumidores no necesariamente se despliegan al mismo tiempo que el servicio. Hace falta una regla explícita de qué cambios son seguros y cómo se comunican los que no lo son.

**Alternativas consideradas.** 
* *Opción A* -- Versionado en la URI (`/v1/...`, `/v2/...`), rompiendo compatibilidad solo al cambiar de versión.
* *Opción B* -- Un solo `/v1/` para siempre, evolucionando el contrato solo con cambios aditivos (nunca se rompe nada, nunca se versiona).

**Decisión.** Versionado explícito en la URI (`/v1/...`), donde el prefijo de versión solo sube cuando hay un cambio incompatible; los cambios compatibles se agregan dentro de la misma versión. [protobuf-proto3]

**Justificación.** El código ya sigue esta convención (`prefix='/v1/clients'`, `prefix='/v1/rentals'`), así que la decisión formaliza lo existente en vez de introducir algo nuevo. Frente a la Opción B, forzar "todo compatible para siempre" no es sostenible: por ejemplo, reemplazar `endDate` por un intervalo con otra semántica sería un cambio incompatible que requiere una versión nueva de la API REST.

**Costo aceptado.** Mantener `/v1/` y una eventual `/v2/` corriendo en paralelo durante el período de migración implica duplicar parcialmente routers y lógica de traducción entre versiones (o al menos mantener ambos hasta deprecar la vieja), y coordinar con los consumidores un aviso de deprecación con plazo antes de apagar `/v1/`.

**Consecuencias.** Se establecen diferencias claras entre versiones y se permite mantenerlas activas en paralelo durante una migración, sin forzar a todos los consumidores a actualizar simultáneamente. Esto requiere adaptar y documentar los contratos, notificar la deprecación y mantener temporalmente las versiones antiguas, con el costo asociado de recursos y mantenimiento. La decisión aplica al versionado REST; la evolución binaria del contrato gRPC sigue además las reglas de Protocol Buffers.

**Evolución del contrato gRPC (`equipos.v1`).** El paquete `equipos.v1` identifica la versión del contrato Protocol Buffers y es independiente del versionado por URI de REST. Si Equipos necesita informar la categoría de una máquina, se puede agregar `string categoria = 5;` al mensaje `Equipo`, conservando los campos existentes (`id = 1`, `nombre = 2`, `descripcion = 3` y `unidades_disponibles = 4`). Es un cambio aditivo compatible: los consumidores antiguos ignoran el campo desconocido; los nuevos consumidores que reciban una respuesta de un servidor antiguo obtienen el valor por defecto de proto3 (`""` para `string`) y deben tolerarlo durante una actualización gradual [protobuf-proto3].

Los números de campo son parte de la identidad binaria del contrato: no se deben renumerar ni reutilizar, ni cambiar el tipo de un campo existente por otro incompatible. Si un campo se retira, se deben reservar su número y su nombre, por ejemplo `reserved 5;` y `reserved "categoria";`, para impedir que una definición futura asigne la misma etiqueta a otro dato. Cambios incompatibles —como alterar la semántica o el tipo de un campo, o retirar un RPC utilizado— requieren una nueva versión del paquete, por ejemplo `equipos.v2`, y una migración coordinada que mantenga disponibles ambas versiones hasta que los consumidores actualicen sus stubs [protobuf-proto3].

Los cambios se comunican versionando el `.proto` junto con las notas de versión y las pruebas de contrato para los consumidores conocidos, incluido el cliente Node.js. Antes de retirar una versión incompatible, se avisa a los consumidores y se establece un período de transición. `equipos.v1` es la versión actual; `equipos.v2` se adoptará solo ante un cambio incompatible real.
