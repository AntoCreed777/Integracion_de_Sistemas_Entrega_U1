from pathlib import Path
import subprocess
import sys

BASE_DIR = Path(__file__).resolve().parent
PROTO_FILE = BASE_DIR / "equipos.proto"
OUTPUT_DIR = BASE_DIR / "generated"


def main():
    if not PROTO_FILE.exists():
        print(f"Archivo .proto no encontrado: {PROTO_FILE}")
        sys.exit(1)

    # Crear carpeta de salida
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    Path(OUTPUT_DIR / "__init__.py").touch()  # Crear archivo __init__.py para que sea un paquete

    command = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{PROTO_FILE.parent}",
        f"--python_out={OUTPUT_DIR}",
        f"--grpc_python_out={OUTPUT_DIR}",
        str(PROTO_FILE),
    ]

    result = subprocess.run(command)

    if result.returncode != 0:
        print(f"Error generando código para {PROTO_FILE}")
        sys.exit(result.returncode)

    print(f"\nCódigo generado correctamente en: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()