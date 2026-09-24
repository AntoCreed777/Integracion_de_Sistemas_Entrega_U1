import os
import pathlib

RESULTS_DIR = pathlib.Path(__file__).parent / "results"
RAW_DIR = RESULTS_DIR / "raw"

BASE_URL = os.getenv("EXPERIMENT_BASE_URL", "http://localhost:8080")
ENDPOINT = os.getenv("EXPERIMENT_ENDPOINT", "/v1/rentals")

REQUESTS = int(os.getenv("EXPERIMENT_REQUESTS", "10000"))
WORKERS = int(os.getenv("EXPERIMENT_WORKERS", "15"))
REPETITIONS = int(os.getenv("EXPERIMENT_REPETITIONS", "10"))
WARMUP_REQUESTS = int(os.getenv("EXPERIMENT_WARMUP_REQUESTS", "100"))

# Header que debe enviar la API para indicar HIT/MISS.
# Ejemplo: X-Cache: HIT / X-Cache: MISS
CACHE_HEADER = "cache_status"

# Para escenarios C/D, si tu API permite seleccionar el recurso mediante
# query parameter, puedes usar por ejemplo:
# EXPERIMENT_ID_PARAM=id
ID_PARAM = os.getenv("EXPERIMENT_ID_PARAM", "id")

# IDs existentes en la BD. El benchmark los utiliza para construir URLs
# distintas cuando se requiere controlar HIT/MISS.
FIRST_ID = int(os.getenv("EXPERIMENT_FIRST_ID", "1"))

HTTP_TIMEOUT = float(os.getenv("EXPERIMENT_HTTP_TIMEOUT", "30"))
