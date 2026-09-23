import argparse
import pathlib
import subprocess

BASE_DIR = pathlib.Path(__file__).parent.parent.resolve()
COMPOSE_FILE = BASE_DIR / "docker-compose.yaml"
ENV_EXAMPLE_FILE = BASE_DIR / ".env.example"
ENV_FILE = BASE_DIR / ".env"


def ensure_env_variables():
    if not ENV_FILE.exists():
        if not ENV_EXAMPLE_FILE.exists():
            raise FileNotFoundError(
                f"El archivo de ejemplo de variables de entorno no existe: {ENV_EXAMPLE_FILE}"
            )
        subprocess.run(["cp", str(ENV_EXAMPLE_FILE), str(ENV_FILE)], check=True)


def set_env_variable(key: str, value: str):
    ensure_env_variables()

    with open(ENV_FILE, "r") as f:
        lines = f.readlines()

    with open(ENV_FILE, "w") as f:
        found = False
        for line in lines:
            if line.startswith(f"{key}="):
                f.write(f"{key}={value}\n")
                found = True
            else:
                f.write(line)

        if not found:
            f.write(f"{key}={value}\n")


def levantar_docker_compose(with_redis: bool = False):
    ensure_env_variables()
    command = ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "--build", "-d"]

    if with_redis:
        set_env_variable("ACTIVATE_REDIS", "true")
    else:
        set_env_variable("ACTIVATE_REDIS", "false")

    subprocess.run(command, check=True)


def detener_docker_compose(delete_volumes: bool = False):
    ensure_env_variables()

    command = ["docker", "compose", "-f", str(COMPOSE_FILE), "down"]
    if delete_volumes:
        command.append("-v")

    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(
        description="Levantar servicios con Docker Compose"
    )

    # Argumentos mutuamente excluyentes para iniciar o detener los servicios
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "-u", "--up", action="store_true", help="Levantar los servicios"
    )
    action_group.add_argument(
        "-d", "--down", action="store_true", help="Detener los servicios"
    )

    # Argumentos adicionales
    parser.add_argument(
        "-v",
        "--delete-volumes",
        action="store_true",
        help="Eliminar volúmenes al detener los servicios",
    )
    parser.add_argument(
        "-r",
        "--with-redis",
        action="store_true",
        help="Levantar el servicio junto con Redis",
    )

    args = parser.parse_args()

    # Validacion de argumentos
    if not args.up and not args.down:
        parser.print_help()
        return

    if args.delete_volumes and not args.down:
        parser.error(
            "La opción --delete-volumes solo tiene efecto al detener los servicios."
        )

    if args.with_redis and not args.up:
        parser.error(
            "La opción --with-redis solo tiene efecto al iniciar los servicios."
        )

    # Ejecutar la acción correspondiente
    if args.up:
        levantar_docker_compose(with_redis=args.with_redis)
    elif args.down:
        detener_docker_compose(delete_volumes=args.delete_volumes)


if __name__ == "__main__":
    main()
