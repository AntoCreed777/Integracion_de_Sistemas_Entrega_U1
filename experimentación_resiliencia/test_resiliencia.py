#!/usr/bin/env python3
"""
Script interactivo de pruebas de resiliencia para la API de FastAPI (arriendos-api)
frente a caídas del servidor gRPC (equipos-api).
"""

import subprocess
import sys
import time
import requests
import atexit

# ---------------------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost:8080"
GRPC_CONTAINER = "equipos-api"

API_KEY_HEADER = "API-Key"
API_KEY_VALUE = "apikey_admin"

HEADERS = {API_KEY_HEADER: API_KEY_VALUE, "Content-Type": "application/json"}

# Debe coincidir con GRPC_TIMEOUT_SECONDS del .env usado por arriendos-api.
GRPC_TIMEOUT_SECONDS = 3

# IDs de prueba: deben existir previamente en las bases de datos correspondientes.
TEST_CLIENT_ID = 1
TEST_EQUIPMENT_ID = 1
TEST_ACTIVE_RENTAL_ID = 1

# Margen para que el cliente HTTP del test no corte antes que la propia API.
REQUEST_TIMEOUT = GRPC_TIMEOUT_SECONDS + 5

# ---------------------------------------------------------------------------
# ESTADO GLOBAL Y LIMPIEZA
# ---------------------------------------------------------------------------

_grpc_is_dummy = False
_grpc_is_paused = False

def cleanup_all():
    """Garantiza que el entorno vuelva a la normalidad si el usuario presiona 'q' o Ctrl+C."""
    if _grpc_is_paused:
        subprocess.run(["docker", "unpause", GRPC_CONTAINER], capture_output=True)
    if _grpc_is_dummy:
        # grpc_start() maneja la eliminación del dummy y restauración del real
        grpc_start()

atexit.register(cleanup_all)

# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

class Colors:
    OK = "\033[92m"
    FAIL = "\033[91m"
    WARN = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"


def log_ok(msg):
    print(f"{Colors.OK}✓ {msg}{Colors.END}")


def log_fail(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.END}")


def log_info(msg):
    print(f"{Colors.CYAN}  -> {msg}{Colors.END}")


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"{Colors.FAIL}Error de Docker: {result.stderr.strip()}{Colors.END}")
    return result.returncode == 0


def grpc_stop():
    global _grpc_is_dummy
    if _grpc_is_dummy:
        return True

    log_info(f"Reemplazando '{GRPC_CONTAINER}' por un clon vacío (simula puerto cerrado / Connection Refused)...")

    # 1. Obtener redes del contenedor original
    cmd_net = [
        "docker", "inspect", 
        "-f", "{{range $k, $v := .NetworkSettings.Networks}}{{$k}}\n{{end}}", 
        GRPC_CONTAINER
    ]
    out = subprocess.run(cmd_net, capture_output=True, text=True).stdout.strip()
    networks = [n for n in out.splitlines() if n]

    if not networks:
        return run(["docker", "stop", GRPC_CONTAINER])

    # 2. Detener y renombrar
    run(["docker", "stop", GRPC_CONTAINER])
    subprocess.run(["docker", "rename", GRPC_CONTAINER, f"{GRPC_CONTAINER}_real"], capture_output=True)

    # 3. Levantar dummy
    cmd_run = ["docker", "run", "-d", "--rm", "--name", GRPC_CONTAINER]
    for net in networks:
        cmd_run.extend(["--network", net])
    cmd_run.extend(["alpine", "sleep", "3600"])

    ok = run(cmd_run)
    if ok:
        _grpc_is_dummy = True
    time.sleep(1)
    return ok


def grpc_start():
    global _grpc_is_dummy
    if not _grpc_is_dummy:
        log_info(f"Verificando encendido de '{GRPC_CONTAINER}'...")
        run(["docker", "start", GRPC_CONTAINER])
        return True

    log_info(f"Restaurando el contenedor original de '{GRPC_CONTAINER}'...")
    subprocess.run(["docker", "stop", GRPC_CONTAINER], capture_output=True)
    subprocess.run(["docker", "rename", f"{GRPC_CONTAINER}_real", GRPC_CONTAINER], capture_output=True)
    
    _grpc_is_dummy = False
    ok = run(["docker", "start", GRPC_CONTAINER])
    time.sleep(2)
    return ok


def grpc_pause():
    global _grpc_is_paused
    log_info(f"Congelando proceso de '{GRPC_CONTAINER}' (docker pause) para simular pérdida de paquetes...")
    ok = run(["docker", "pause", GRPC_CONTAINER])
    if ok:
        _grpc_is_paused = True
    return ok


def grpc_unpause():
    global _grpc_is_paused
    if not _grpc_is_paused:
        return True
    log_info(f"Descongelando contenedor '{GRPC_CONTAINER}' (docker unpause)...")
    ok = run(["docker", "unpause", GRPC_CONTAINER])
    if ok:
        _grpc_is_paused = False
    return ok


def wait_for_api_health(timeout=30):
    log_info("Comprobando que arriendos-api esté online (endpoint /health)...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=3)
            if r.status_code == 200:
                log_info("arriendos-api está respondiendo.")
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    log_fail("arriendos-api no respondió a tiempo.")
    return False


def create_rental_payload():
    return {
        "clientId": TEST_CLIENT_ID,
        "equipmentId": TEST_EQUIPMENT_ID,
        "startDate": "2026-10-01T00:00:00Z",
        "endDate": "2026-10-10T00:00:00Z",
    }

# ---------------------------------------------------------------------------
# SISTEMA INTERACTIVO Y RESULTADOS
# ---------------------------------------------------------------------------

results = []

def record(name, condition, detail=""):
    if condition:
        log_ok(f"{name} {detail}")
    else:
        log_fail(f"{name} {detail}")
    results.append((name, condition))


def prompt_user(test_title, test_desc, expected_result):
    print("\n" + "=" * 80)
    print(f"{Colors.BOLD}{Colors.CYAN}{test_title}{Colors.END}")
    print("-" * 80)
    print(f"{Colors.BOLD}Escenario:{Colors.END} {test_desc}")
    print(f"{Colors.BOLD}Esperado:{Colors.END}  {expected_result}")
    print("-" * 80)
    
    while True:
        resp = input(f"{Colors.WARN}Presiona [Enter] para EJECUTAR o escribe 'q' para ABORTAR: {Colors.END}").strip().lower()
        if resp == 'q':
            print("\nCancelando pruebas... Restaurando contenedores a su estado normal.")
            sys.exit(0) # Esto dispara cleanup_all() vía atexit
        elif resp == '':
            print("") # Salto de línea limpio
            break


# ---------------------------------------------------------------------------
# CASOS DE PRUEBA
# ---------------------------------------------------------------------------

def test_baseline():
    try:
        r = requests.post(
            f"{BASE_URL}/v1/rentals",
            json=create_rental_payload(),
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        record("create_rental responde exitosamente (201 o 409)", r.status_code in (201, 409), f"Status={r.status_code}")
    except requests.RequestException as e:
        record("Error de conexión con la API HTTP", False, str(e))
 
 
def test_grpc_down_stop():
    grpc_stop()
    try:
        start = time.time()
        r = requests.post(
            f"{BASE_URL}/v1/rentals",
            json=create_rental_payload(),
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        elapsed = time.time() - start
        
        record("Devuelve código HTTP 503 (Servicio no disponible)", r.status_code == 503, f"Status={r.status_code}")
        record("Rechaza rápido sin colgarse", elapsed < 1.0, f"(Demoró {elapsed:.2f}s)")
        
    except requests.exceptions.Timeout:
        record("La petición falló", False, "El test dio Timeout, la API se quedó colgada.")
    except requests.RequestException as e:
        record("Error HTTP", False, str(e))
 
 
def test_grpc_slow_pause():
    grpc_start()
    if not wait_for_api_health(): return
    
    grpc_pause()
    try:
        start = time.time()
        r = requests.post(
            f"{BASE_URL}/v1/rentals",
            json=create_rental_payload(),
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        elapsed = time.time() - start
        
        record("Devuelve código HTTP 504 (Gateway Timeout)", r.status_code == 504, f"Status={r.status_code}")
        record(f"Respeta el timeout configurado (~{GRPC_TIMEOUT_SECONDS}s)", 
               GRPC_TIMEOUT_SECONDS - 0.5 <= elapsed <= GRPC_TIMEOUT_SECONDS + 3, 
               f"(Demoró {elapsed:.2f}s)")
               
    except requests.exceptions.Timeout:
        record("Timeout del lado de test", False, f"La API superó los {REQUEST_TIMEOUT}s de gracia sin responder.")
    finally:
        grpc_unpause()
 
 
def test_health_endpoint_stays_up():
    grpc_stop()
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        record("El endpoint /health responde 200 OK", r.status_code == 200, f"Status={r.status_code}")
    except requests.RequestException as e:
        record("El endpoint /health falló", False, str(e))
 
 
def test_recovery():
    grpc_start()
    if not wait_for_api_health(): return
    time.sleep(2) # Darle un segundo extra para restablecer conexiones gRPC
    
    try:
        r = requests.post(
            f"{BASE_URL}/v1/rentals",
            json=create_rental_payload(),
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        record("Operaciones vuelven a funcionar sin reiniciar FastAPI", r.status_code in (201, 409), f"Status={r.status_code}")
    except requests.RequestException as e:
        record("Fallo reconexión", False, str(e))
 
 
def test_cancel_not_found_with_grpc_down():
    grpc_stop()
    try:
        r = requests.post(
            f"{BASE_URL}/v1/rentals/99999999/cancel",
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        record("Falla por validación local (404) y no por gRPC (503)", r.status_code == 404, f"Status={r.status_code}")
    except requests.RequestException as e:
        record("Error inesperado", False, str(e))
 
 
def test_cancel_active_with_grpc_down():
    # Aseguramos que siga usando el contenedor dummy del test anterior
    try:
        start = time.time()
        r = requests.post(
            f"{BASE_URL}/v1/rentals/{TEST_ACTIVE_RENTAL_ID}/cancel",
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        elapsed = time.time() - start
        
        record("Falla en la llamada gRPC arrojando 503 rápido", r.status_code == 503, f"Status={r.status_code}")
        record("Rechaza rápido sin colgarse", elapsed < 1.0, f"(Demoró {elapsed:.2f}s)")
    except requests.RequestException as e:
        record("Fallo inesperado", False, str(e))
    finally:
        grpc_start()
        wait_for_api_health()


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print(f"{Colors.BOLD}Iniciando validación de dependencias iniciales...{Colors.END}")
    if not wait_for_api_health():
        log_fail("arriendos-api no está disponible. Revisa si está corriendo.")
        sys.exit(1)

    # TEST 1
    prompt_user(
        test_title="TEST 1: Sistema sano (Baseline)",
        test_desc="Verifica que gRPC y la API estén funcionando correctamente antes de iniciar los cortes.",
        expected_result="La creación de arriendo devuelve 201 (Creado) o 409 (Conflicto si ya existe)."
    )
    test_baseline()

    # TEST 2
    prompt_user(
        test_title="TEST 2: Caída con rechazo rápido (Connection Refused)",
        test_desc="Sustituye 'equipos-api' por un clon vacío (dummy). La máquina existe y recibe el paquete en su red, pero al tener el puerto cerrado, rechaza instantáneamente la conexión (TCP RST).",
        expected_result="La API debe fallar en nanosegundos (gRPC UNAVAILABLE) y devolver 503 sin bloquearse."
    )
    test_grpc_down_stop()

    # TEST 3
    prompt_user(
        test_title="TEST 3: Congelamiento (Timeout Exceeded)",
        test_desc="El contenedor gRPC se pausa (docker pause). No rechaza la conexión, los paquetes simplemente se pierden. El sistema FastAPI queda esperando en el aire.",
        expected_result="FastAPI debe esperar máximo su GRPC_TIMEOUT_SECONDS (aprox 3s) y arrojar 504 (Gateway Timeout), evitando quedarse congelado indefinidamente."
    )
    test_grpc_slow_pause()

    # TEST 4
    prompt_user(
        test_title="TEST 4: Independencia del endpoint /health",
        test_desc="Mantenemos el contenedor dummy de gRPC activo. Hacemos un GET al endpoint de estado (/health).",
        expected_result="Debe responder 200 OK inmediatamente. Kubernetes o el Load Balancer no deben creer que 'arriendos-api' murió solo porque perdió conexión con un microservicio."
    )
    test_health_endpoint_stays_up()

    # TEST 5
    prompt_user(
        test_title="TEST 5: Recuperación automática (Self-healing)",
        test_desc="Restauramos el contenedor 'equipos-api' original y volvemos a intentar una creación.",
        expected_result="FastAPI debe reconectarse solo al canal gRPC y procesar la petición correctamente (201/409), sin que un humano tenga que reiniciar el contenedor arriendos-api."
    )
    test_recovery()

    # TEST 6A
    prompt_user(
        test_title="TEST 6a: Cancelación (Validación local primero)",
        test_desc="Con gRPC caído de nuevo (dummy), intentamos cancelar un arriendo con un ID que NO existe en la base de datos de arriendos.",
        expected_result="Debe fallar con 404 (Not Found) inmediatamente, demostrando que la API no hace peticiones gRPC innecesarias si la validación local falla."
    )
    test_cancel_not_found_with_grpc_down()

    # TEST 6B
    prompt_user(
        test_title="TEST 6b: Cancelación (Dependencia gRPC requerida)",
        test_desc="Intentamos cancelar un arriendo que SÍ existe (Active). Esto requiere comunicarse por gRPC para notificar la liberación del equipo, pero gRPC sigue caído.",
        expected_result="Debe devolver 503 rápidamente debido a Connection Refused."
    )
    test_cancel_active_with_grpc_down()

    print("\n" + "=" * 80)
    print(f"{Colors.BOLD}RESUMEN FINAL DE LA EJECUCIÓN{Colors.END}")
    print("=" * 80)
    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    
    for name, ok in results:
        (log_ok if ok else log_fail)(name)
        
    color_res = Colors.OK if passed == total else Colors.FAIL
    print(f"\n{color_res}{passed} de {total} verificaciones pasaron exitosamente.{Colors.END}\n")

    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()