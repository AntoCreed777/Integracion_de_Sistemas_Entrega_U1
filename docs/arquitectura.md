# Arquitectura y descomposición en servicios

```mermaid
flowchart TB
    subgraph consumidores["Consumidores"]
        direction LR
        usuario["Cliente HTTP\nConsumidor de la API"]
        node["cliente-node\nCliente gRPC de interoperabilidad"]
    end

    subgraph plataforma["Plataforma de arriendos"]
        direction LR

        subgraph arriendos["Servicio Arriendos · FastAPI · REST :8080"]
            direction TB
            api["API REST\n/health · /v1/clients · /v1/rentals"]
            auth["Autenticación y autorización\nAPI-Key / roles"]

            subgraph logicaArriendos["Lógica de aplicación"]
                direction LR
                rental["Arriendos\ncrear · consultar · cancelar · retornar"]
                clients["Clientes\ncrear · listar · consultar"]
                grpcclient["Cliente gRPC\nreservar_unidad / liberar_unidad"]
            end

            ormRentals["SQLAlchemy\nModelos Client y Rental"]

            subgraph datosArriendos["Datos y cache"]
                direction LR
                arriendosDB[("PostgreSQL\nBase de arriendos")]
                redis[("Redis\nCache opcional de consultas")]
            end
        end

        subgraph equipos["Servicio Equipos · Python gRPC · :50051"]
            direction TB
            grpcapi["Servicio Equipos\nConsultarEquipo · ConsultarDisponibilidadEquipo\nListarEquipos · ReservarEquipo · LiberarEquipo"]
            health["gRPC Health Check"]
            equipment["Dominio de equipos\nCatálogo y control de stock"]
            ormEquipment["SQLAlchemy\nModelo Equipo"]
            equiposDB[("PostgreSQL\nBase de equipos")]
        end
    end

    usuario -->|"HTTP / JSON → API REST"| api
    node -->|"gRPC / protobuf → Servicio Equipos"| grpcapi

    api --> auth
    auth --> rental
    auth --> clients
    rental --> ormRentals
    clients --> ormRentals
    ormRentals -->|"SQL"| arriendosDB

    rental -->|"lecturas: HIT / MISS"| redis
    rental -->|"invalidación tras mutaciones"| redis
    rental --> grpcclient
    grpcclient -->|"gRPC / protobuf\nEQUIPOS_GRPC_URL"| grpcapi

    grpcapi --> equipment
    grpcapi --> health
    equipment --> ormEquipment
    ormEquipment -->|"SQL"| equiposDB

    classDef consumer fill:#e8f1f8,stroke:#35627a,color:#173042
    classDef service fill:#fff3d6,stroke:#b7791f,color:#3d2a0b
    classDef module fill:#f4efe6,stroke:#8c7355,color:#30271e
    classDef data fill:#e8f5e9,stroke:#39734a,color:#17351f
    classDef protocol fill:#f1e8f8,stroke:#76508a,color:#2f1b3b

    class usuario,node consumer
    class arriendos,equipos service
    class logicaArriendos,datosArriendos protocol
    class api,auth,rental,clients,grpcclient,grpcapi,health,equipment,ormRentals,ormEquipment module
    class arriendosDB,redis,equiposDB data
```

## Flujos principales

- **Crear arriendo:** `Cliente HTTP -> arriendos-api -> PostgreSQL de arriendos` y, antes de confirmar, `arriendos-api -> equipos-api -> PostgreSQL de equipos` para reservar una unidad.
- **Consultar arriendos:** `arriendos-api` intenta resolver desde Redis cuando está activo; ante un `MISS`, consulta PostgreSQL y almacena el resultado durante 60 segundos.
- **Cancelar o retornar:** `arriendos-api` libera la unidad mediante gRPC, actualiza el estado local y elimina las entradas de cache relacionadas.
- **Interoperabilidad:** `cliente-node` consume directamente el contrato `Equipos/equipos.proto` y prueba las operaciones gRPC del catálogo.

La separación de datos es por servicio: cada API posee su propia base PostgreSQL y el servicio Arriendos no accede directamente a la base de Equipos. La comunicación entre servicios se realiza exclusivamente mediante gRPC.
