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
