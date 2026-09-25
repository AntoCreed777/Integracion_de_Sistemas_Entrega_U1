# Arquitectura y descomposición en servicios

```mermaid
flowchart TB
    usuario["Cliente HTTP / consumidor de la API"]
    node["cliente-node\nCliente gRPC de interoperabilidad"]

    subgraph plataforma["Plataforma de arriendos"]
        subgraph arriendos["Servicio Arriendos - FastAPI\nREST :8080"]
            api["API REST\n/health\n/v1/clients\n/v1/rentals"]
            auth["Autenticación y autorización\nAPI-Key / roles"]
            rental["Módulo de arriendos\ncrear, consultar, cancelar y retornar"]
            clients["Módulo de clientes\ncrear, listar y consultar"]
            grpcclient["Cliente gRPC\nreservar_unidad / liberar_unidad"]
            ormRentals["SQLAlchemy / modelos\nClient y Rental"]
        end

        arriendosDB[("PostgreSQL\nBase de arriendos")]
        redis[("Redis\nCache opcional de consultas")]

        subgraph equipos["Servicio Equipos - Python gRPC\n:50051"]
            grpcapi["ServicioEquipos\nConsultarEquipo\nConsultarDisponibilidadEquipo\nListarEquipos\nReservarEquipo\nLiberarEquipo"]
            health["gRPC Health Check"]
            equipment["Dominio de equipos\ncatálogo y control de stock"]
            ormEquipment["SQLAlchemy / modelo Equipo"]
        end

        equiposDB[("PostgreSQL\nBase de equipos")]
    end

    usuario -->|"HTTP/JSON"| api
    api --> auth
    auth --> rental
    auth --> clients
    rental --> ormRentals
    clients --> ormRentals
    ormRentals -->|"SQL"| arriendosDB

    rental -->|"lecturas: HIT/MISS"| redis
    rental -->|"invalidación después de mutaciones"| redis

    rental --> grpcclient
    grpcclient -->|"gRPC / protobuf\nEQUIPOS_GRPC_URL"| grpcapi
    grpcapi --> equipment
    grpcapi --> health
    equipment --> ormEquipment
    ormEquipment -->|"SQL"| equiposDB

    node -->|"gRPC / protobuf\nServicioEquipos"| grpcapi

    classDef consumer fill:#e8f1f8,stroke:#35627a,color:#173042
    classDef service fill:#fff3d6,stroke:#b7791f,color:#3d2a0b
    classDef module fill:#f4efe6,stroke:#8c7355,color:#30271e
    classDef data fill:#e8f5e9,stroke:#39734a,color:#17351f
    classDef protocol fill:#f1e8f8,stroke:#76508a,color:#2f1b3b

    class usuario,node consumer
    class arriendos,equipos service
    class api,auth,rental,clients,grpcclient,grpcapi,health,equipment,ormRentals,ormEquipment module
    class arriendosDB,redis,equiposDB data

    linkStyle 7,8,9,10 stroke:#76508a,stroke-width:2px
```

## Flujos principales

- **Crear arriendo:** `Cliente HTTP -> arriendos-api -> PostgreSQL de arriendos` y, antes de confirmar, `arriendos-api -> equipos-api -> PostgreSQL de equipos` para reservar una unidad.
- **Consultar arriendos:** `arriendos-api` intenta resolver desde Redis cuando está activo; ante un `MISS`, consulta PostgreSQL y almacena el resultado durante 60 segundos.
- **Cancelar o retornar:** `arriendos-api` libera la unidad mediante gRPC, actualiza el estado local y elimina las entradas de cache relacionadas.
- **Interoperabilidad:** `cliente-node` consume directamente el contrato `Equipos/equipos.proto` y prueba las operaciones gRPC del catálogo.

La separación de datos es por servicio: cada API posee su propia base PostgreSQL y el servicio Arriendos no accede directamente a la base de Equipos. La comunicación entre servicios se realiza exclusivamente mediante gRPC.
