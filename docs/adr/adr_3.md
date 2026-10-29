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
