import argparse
import asyncio
import csv
import os
import pathlib
import sys
import time
from dataclasses import dataclass
from typing import Any

from enum import Enum, auto
import httpx
import numpy as np

from dotenv import load_dotenv
load_dotenv()

sys.path.append(str(pathlib.Path(__file__).parent.parent.resolve()))


from experiment_latencia.docker_aux import detener_docker_compose, levantar_docker_compose
from experiment_latencia.fill_db import fill_database

try:
    from scipy.stats import wilcoxon
except ImportError:
    wilcoxon = None


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

RESULTS_DIR = pathlib.Path(__file__).parent / "results"
RAW_DIR = RESULTS_DIR / "raw"

BASE_URL = os.getenv("EXPERIMENT_BASE_URL", "http://localhost:8080")
ENDPOINT = os.getenv("EXPERIMENT_ENDPOINT", "/v1/clients")

REQUESTS = int(os.getenv("EXPERIMENT_REQUESTS", "1000"))
WORKERS = int(os.getenv("EXPERIMENT_WORKERS", "10"))
REPETITIONS = int(os.getenv("EXPERIMENT_REPETITIONS", "5"))
WARMUP_REQUESTS = int(os.getenv("EXPERIMENT_WARMUP_REQUESTS", "100"))

# Header que debe enviar la API para indicar HIT/MISS.
# Ejemplo: X-Cache: HIT / X-Cache: MISS
CACHE_HEADER = os.getenv("EXPERIMENT_CACHE_HEADER", "X-Cache")

# Para escenarios C/D, si tu API permite seleccionar el recurso mediante
# query parameter, puedes usar por ejemplo:
# EXPERIMENT_ID_PARAM=id
ID_PARAM = os.getenv("EXPERIMENT_ID_PARAM", "id")

# IDs existentes en la BD. El benchmark los utiliza para construir URLs
# distintas cuando se requiere controlar HIT/MISS.
FIRST_ID = int(os.getenv("EXPERIMENT_FIRST_ID", "1"))

HTTP_TIMEOUT = float(os.getenv("EXPERIMENT_HTTP_TIMEOUT", "30"))


@dataclass
class RequestResult:
    request_id: int
    latency_ms: float
    status_code: int | None
    cache_status: str | None
    error: str | None = None


def build_url(resource_id: int | None = None) -> str:
    url = BASE_URL.rstrip("/") + "/" + ENDPOINT.lstrip("/")

    if resource_id is not None:
        url = url.lstrip("/") + str(resource_id)

    return url


async def fetch(
    client: httpx.AsyncClient,
    url: str,
    request_id: int,
) -> RequestResult:
    start = time.perf_counter()

    try:
        response = await client.get(url)
        elapsed = (time.perf_counter() - start) * 1000

        return RequestResult(
            request_id=request_id,
            latency_ms=elapsed,
            status_code=response.status_code,
            cache_status=response.headers.get(CACHE_HEADER),
        )

    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000

        return RequestResult(
            request_id=request_id,
            latency_ms=elapsed,
            status_code=None,
            cache_status=None,
            error=f"{type(exc).__name__}: {exc}",
        )


async def worker(
    client: httpx.AsyncClient,
    queue: asyncio.Queue,
    results: list[RequestResult],
):
    while True:
        request_id, url = await queue.get()

        try:
            result = await fetch(
                client=client,
                url=url,
                request_id=request_id,
            )
            results.append(result)
        finally:
            queue.task_done()


async def run_requests(urls: list[str]) -> tuple[list[RequestResult], float]:
    queue = asyncio.Queue()

    for request_id, url in enumerate(urls):
        await queue.put((request_id, url))

    results: list[RequestResult] = []

    limits = httpx.Limits(
        max_connections=WORKERS,
        max_keepalive_connections=WORKERS,
    )

    timeout = httpx.Timeout(HTTP_TIMEOUT)

    start = time.perf_counter()

    async with httpx.AsyncClient(
        limits=limits,
        timeout=timeout,
    ) as client:

        workers = [
            asyncio.create_task(worker(client, queue, results)) for _ in range(WORKERS)
        ]

        await queue.join()

        elapsed = time.perf_counter() - start

        for task in workers:
            task.cancel()

        await asyncio.gather(
            *workers,
            return_exceptions=True,
        )

    return results, elapsed


async def warmup(url: str):
    if WARMUP_REQUESTS <= 0:
        return

    print(f"[WARM-UP] {WARMUP_REQUESTS} requests...")

    urls = [url for _ in range(WARMUP_REQUESTS)]

    results, _ = await run_requests(urls)

    errors = sum(1 for result in results if result.error is not None)

    print(f"[WARM-UP] completado. errores={errors}")


# ---------------------------------------------------------------------------
# Preparación de escenarios
# ---------------------------------------------------------------------------

class Scenario(Enum):
    A = auto()  # mismo recurso, sin Redis.
    B = auto()  # mismo recurso repetido; Redis debe estar precargado.
    C = auto()  # recursos distintos, que no deben estar previamente en Redis.
    D = auto()  # mitad de recursos precargados y mitad nuevos.
    ALL = auto()  # Ejecuta todos los escenarios.


def scenario_urls(scenario: Scenario) -> list[str]:
    """
    Construye las URLs de cada escenario.
    """
    if scenario in (Scenario.A, Scenario.B):
        url = build_url(FIRST_ID)
        return [url] * REQUESTS

    if scenario == Scenario.C:
        return [build_url(FIRST_ID + i) for i in range(REQUESTS)]

    if scenario == Scenario.D:
        half = REQUESTS // 2

        urls = [build_url(FIRST_ID + i) for i in range(half)]
        urls *= 2  # duplicar, de esta forma, aprox la mitad sera MISS y la otra mitad será HIT.

        if len(urls) < REQUESTS:
            urls += [build_url(FIRST_ID + half)] * (REQUESTS - len(urls))   # No deberia de ser mas de 1, pero por si acaso.

        return urls[:REQUESTS]

    raise ValueError(f"Escenario desconocido: {scenario}")


async def prepare_cache_hit():
    """
    Genera una solicitud al recurso que se utilizará como HIT.

    Después de esta función el recurso debería estar en Redis.
    """
    url = build_url(FIRST_ID)

    print(f"[CACHE] Precalentando recurso HIT: {url}")

    limits = httpx.Limits(max_connections=1, max_keepalive_connections=1)

    async with httpx.AsyncClient(
        limits=limits,
        timeout=HTTP_TIMEOUT,
    ) as client:
        response = await client.get(url)

        print(
            "[CACHE] status=%s cache=%s"
            % (
                response.status_code,
                response.headers.get(CACHE_HEADER),
            )
        )


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------


def calculate_metrics(
    results: list[RequestResult],
    total_time_s: float,
) -> dict[str, Any]:

    valid = [result for result in results if result.error is None]

    latencies = np.array(
        [result.latency_ms for result in valid],
        dtype=float,
    )

    if len(latencies) == 0:
        raise RuntimeError("No existen requests válidas para calcular métricas.")

    errors = len(results) - len(valid)

    metrics = {
        "requests": len(results),
        "successful_requests": len(valid),
        "errors": errors,
        "total_time_s": total_time_s,
        "rps": len(results) / total_time_s if total_time_s > 0 else 0,
        "mean_ms": float(np.mean(latencies)),
        "std_ms": float(np.std(latencies, ddof=1)) if len(latencies) > 1 else 0.0,
        "p1_ms": float(np.percentile(latencies, 1)),
        "p5_ms": float(np.percentile(latencies, 5)),
        "p25_ms": float(np.percentile(latencies, 25)),
        "p50_ms": float(np.percentile(latencies, 50)),
        "p75_ms": float(np.percentile(latencies, 75)),
        "p95_ms": float(np.percentile(latencies, 95)),
        "p99_ms": float(np.percentile(latencies, 99)),
    }

    hits = sum(1 for result in valid if (result.cache_status or "").upper() == "HIT")

    misses = sum(1 for result in valid if (result.cache_status or "").upper() == "MISS")

    cache_observed = hits + misses

    metrics["cache_hits"] = hits
    metrics["cache_misses"] = misses
    metrics["hit_rate_pct"] = (
        hits / cache_observed * 100 if cache_observed > 0 else None
    )

    return metrics


def save_raw_results(
    scenario: Scenario,
    repetition: int,
    results: list[RequestResult],
):
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    path = RAW_DIR / f"{scenario.name}_rep{repetition}.csv"

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "request_id",
                "latency_ms",
                "status_code",
                "cache_status",
                "error",
            ],
        )

        writer.writeheader()

        for result in results:
            writer.writerow(
                {
                    "request_id": result.request_id,
                    "latency_ms": result.latency_ms,
                    "status_code": result.status_code,
                    "cache_status": result.cache_status,
                    "error": result.error,
                }
            )

    return path


# ---------------------------------------------------------------------------
# Ejecución de un escenario
# ---------------------------------------------------------------------------


async def execute_scenario(scenario: Scenario):
    with_redis = scenario != Scenario.A

    print()
    print("=" * 70)
    print(f"ESCENARIO {scenario.name}")
    print("=" * 70)

    levantar_docker_compose(with_redis=with_redis)

    # Esperar a que la aplicación esté disponible.
    await wait_for_api()

    if scenario == Scenario.B:
        # Para B queremos que el recurso ya esté en Redis.
        await prepare_cache_hit()

    for repetition in range(1, REPETITIONS + 1):
        print()
        print(f"[{scenario.name}] Repetición " f"{repetition}/{REPETITIONS}")

        if scenario == Scenario.B:
            # Garantiza que el recurso siga caliente antes de la medición.
            await prepare_cache_hit()

        # Warm-up separado de la medición.
        await warmup(build_url(FIRST_ID))

        urls = scenario_urls(scenario)

        results, total_time = await run_requests(urls)

        metrics = calculate_metrics(
            results=results,
            total_time_s=total_time,
        )

        raw_path = save_raw_results(
            scenario=scenario,
            repetition=repetition,
            results=results,
        )

        print_metrics(
            scenario=scenario,
            repetition=repetition,
            metrics=metrics,
        )

        save_summary_row(
            scenario=scenario,
            repetition=repetition,
            metrics=metrics,
        )

        print(f"[RAW] {raw_path}")


async def wait_for_api():
    url = build_url()

    print(f"[API] Esperando disponibilidad de {url}...")

    timeout = time.monotonic() + 60

    while time.monotonic() < timeout:
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.get(url)

                if response.status_code < 500:
                    print("[API] Disponible.")
                    return

        except Exception:
            pass

        await asyncio.sleep(1)

    raise RuntimeError("La API no estuvo disponible después de 60 segundos.")


def print_metrics(
    scenario: Scenario,
    repetition: int,
    metrics: dict[str, Any],
):
    print(f"""
[RESULTADO]
Escenario:       {scenario.name}
Repetición:      {repetition}
Requests:        {metrics["requests"]}
Errores:         {metrics["errors"]}

Media:           {metrics["mean_ms"]:.4f} ms
Desv. estándar:  {metrics["std_ms"]:.4f} ms

P1:              {metrics["p1_ms"]:.4f} ms
P5:              {metrics["p5_ms"]:.4f} ms
P25:             {metrics["p25_ms"]:.4f} ms
P50:             {metrics["p50_ms"]:.4f} ms
P75:             {metrics["p75_ms"]:.4f} ms
P95:             {metrics["p95_ms"]:.4f} ms
P99:             {metrics["p99_ms"]:.4f} ms

RPS:             {metrics["rps"]:.4f}
Tiempo total:    {metrics["total_time_s"]:.4f} s

Cache HIT:       {metrics["cache_hits"]}
Cache MISS:      {metrics["cache_misses"]}
Hit rate:        {metrics["hit_rate_pct"] if metrics["hit_rate_pct"] is not None else "N/A"}
""")


# ---------------------------------------------------------------------------
# Resumen y análisis estadístico
# ---------------------------------------------------------------------------

SUMMARY_FIELDS = [
    "scenario",
    "repetition",
    "requests",
    "successful_requests",
    "errors",
    "total_time_s",
    "rps",
    "mean_ms",
    "std_ms",
    "p1_ms",
    "p5_ms",
    "p25_ms",
    "p50_ms",
    "p75_ms",
    "p95_ms",
    "p99_ms",
    "cache_hits",
    "cache_misses",
    "hit_rate_pct",
]


def save_summary_row(
    scenario: Scenario,
    repetition: int,
    metrics: dict[str, Any],
):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    path = RESULTS_DIR / "summary.csv"

    exists = path.exists()

    with path.open(
        "a",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=SUMMARY_FIELDS,
        )

        if not exists:
            writer.writeheader()

        row = {
            "scenario": scenario.name,
            "repetition": repetition,
        }

        row.update(metrics)

        writer.writerow(row)


def load_summary() -> list[dict[str, str]]:
    path = RESULTS_DIR / "summary.csv"

    if not path.exists():
        return []

    with path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:
        return list(csv.DictReader(file))


def paired_values(
    rows: list[dict[str, str]],
    scenario_a: Scenario,
    scenario_b: Scenario,
    metric: str,
):
    a = {}
    b = {}

    for row in rows:
        repetition = int(row["repetition"])
        value = float(row[metric])

        if row["scenario"] == scenario_a.name:
            a[repetition] = value

        elif row["scenario"] == scenario_b.name:
            b[repetition] = value

    repetitions = sorted(set(a.keys()) & set(b.keys()))

    return (
        [a[r] for r in repetitions],
        [b[r] for r in repetitions],
        repetitions,
    )


def generate_statistical_analysis():
    rows = load_summary()

    if not rows:
        print("[STATS] No hay resultados.")
        return

    output = []

    output.append("ANÁLISIS ESTADÍSTICO DEL EXPERIMENTO\n")

    output.append("Nivel de significancia: alpha = 0.05\n")

    output.append(
        "La comparación inferencial utiliza los valores agregados "
        "por repetición (n=5 por escenario), evitando tratar las "
        "solicitudes concurrentes dentro de una misma ejecución como "
        "observaciones independientes.\n"
    )

    comparisons = [
        (Scenario.A, Scenario.B, "Sin cache vs HIT"),
        (Scenario.A, Scenario.C, "Sin cache vs MISS"),
        (Scenario.A, Scenario.D, "Sin cache vs HIT/MISS"),
    ]

    for scenario_a, scenario_b, title in comparisons:
        output.append("=" * 70)
        output.append(title)
        output.append("=" * 70)

        for metric in [
            "mean_ms",
            "p50_ms",
            "p95_ms",
            "p99_ms",
            "rps",
        ]:
            a, b, repetitions = paired_values(
                rows,
                scenario_a,
                scenario_b,
                metric,
            )

            if len(a) < 2:
                output.append(f"{metric}: datos insuficientes.\n")
                continue

            output.append(
                f"{metric}:\n" f"  A ({scenario_a}): {a}\n" f"  B ({scenario_b}): {b}\n"
            )

            if wilcoxon is not None:
                try:
                    statistic, p_value = wilcoxon(
                        b,
                        a,
                        alternative="less",
                    )

                    output.append(
                        f"  Wilcoxon pareado, H1: {scenario_b} < {scenario_a}\n"
                        f"  statistic = {statistic:.6f}\n"
                        f"  p-value   = {p_value:.6f}\n"
                        f"  significativo (alpha=0.05): "
                        f"{p_value < 0.05}\n"
                    )

                except ValueError as exc:
                    output.append(f"  Wilcoxon no calculable: {exc}\n")

            else:
                output.append("  scipy no está instalado; no se calculó Wilcoxon.\n")

            output.append("")

    output_path = RESULTS_DIR / "statistical_analysis.txt"

    output_path.write_text(
        "\n".join(output),
        encoding="utf-8",
    )

    print(f"[STATS] {output_path}")


# ---------------------------------------------------------------------------
# Ejecución completa
# ---------------------------------------------------------------------------


async def run_all():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Evitar mezclar resultados de ejecuciones anteriores.
    summary = RESULTS_DIR / "summary.csv"

    if summary.exists():
        summary.unlink()

    scenarios = [Scenario.A, Scenario.B, Scenario.C, Scenario.D]

    for scenario in scenarios:
        try:
            await execute_scenario(scenario)

        finally:
            # Dejamos Docker detenido al terminar cada escenario.
            # No eliminamos volúmenes para conservar la BD entre escenarios.
            detener_docker_compose(delete_volumes=False)

    generate_statistical_analysis()


async def run_one(scenario: Scenario):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    await execute_scenario(scenario)

    generate_statistical_analysis()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description=("Experimento de latencia para evaluar Redis como caché.")
    )

    parser.add_argument(
        "--scenario",
        type=Scenario,
        choices=list(Scenario),
        default=Scenario.ALL,
        help=("Escenario a ejecutar: " "A=sin cache, B=HIT, C=MISS, D=50/50."),
    )

    parser.add_argument(
        "--fill-db",
        type=int,
        metavar="N",
        help="Inserta N equipos antes de ejecutar el experimento.",
    )

    parser.add_argument(
        "--down",
        action="store_true",
        help="Detiene Docker y termina.",
    )

    parser.add_argument(
        "--delete-volumes",
        action="store_true",
        help="Al usar --down elimina también los volúmenes.",
    )

    args = parser.parse_args()

    if args.down:
        detener_docker_compose(delete_volumes=args.delete_volumes)
        return

    if args.fill_db:
        fill_database(args.fill_db)

    if args.scenario == Scenario.ALL:
        asyncio.run(run_all())
    else:
        asyncio.run(run_one(args.scenario))


if __name__ == "__main__":
    main()
