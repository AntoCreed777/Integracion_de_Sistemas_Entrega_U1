import os
import time


def main() -> None:
    host = os.getenv("DATABASE_HOST", "equipos-db")
    port = os.getenv("DATABASE_PORT", "5432")
    database = os.getenv("DATABASE_NAME", os.getenv("POSTGRES_DB", "equipos_db"))

    print("Microservicio Equipos iniciado")
    print(f"Base de datos configurada en {host}:{port}/{database}")
    print("Reemplaza app/main.py por el servidor gRPC cuando esté listo.")

    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
