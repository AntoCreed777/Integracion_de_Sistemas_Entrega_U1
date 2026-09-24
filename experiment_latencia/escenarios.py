import asyncio
import time
from unittest import case

import httpx

from experiment_latencia.config import (
    CACHE_HEADER,
    FIRST_ID,
    HTTP_TIMEOUT,
    REPETITIONS,
    REQUESTS,
)
from experiment_latencia.docker_aux import (
    docker_services_healthy,
    levantar_docker_compose,
)
from experiment_latencia.metricas import (
    calculate_metrics,
    print_metrics,
    save_raw_results,
    save_summary_row,
)
from experiment_latencia.requests import build_url, run_requests, warmup
from experiment_latencia.modelos import Scenario
from experiment_latencia.fill_db import fill_database




def scenario_urls(scenario: Scenario) -> list[str]:
    """
    Construye las URLs de cada escenario.
    """
    if scenario in (Scenario.A, Scenario.B):
        url = build_url(FIRST_ID)
        return [url] * REQUESTS

    elif scenario == Scenario.C:
        return [build_url(FIRST_ID + i) for i in range(REQUESTS)]

    elif scenario == Scenario.D:
        half = REQUESTS // 2

        urls = [build_url(FIRST_ID + i) for i in range(half)]
        urls *= 2  # duplicar, de esta forma, aprox la mitad sera MISS y la otra mitad será HIT.

        if len(urls) < REQUESTS:
            urls += [build_url(FIRST_ID + half)] * (
                REQUESTS - len(urls)
            )  # No deberia de ser mas de 1, pero por si acaso.

        return urls[:REQUESTS]

    raise ValueError(f"Escenario desconocido: {scenario}")


async def execute_scenario(scenario: Scenario):
    with_redis = scenario != Scenario.A

    print()
    print("=" * 70)
    print(f"ESCENARIO {scenario.name}")
    print("=" * 70)

    levantar_docker_compose(with_redis=with_redis)

    reintentos = 0
    while True:
        if docker_services_healthy():
            break
        else:
            print()
            print("[DOCKER] Reintentando en 2 segundos...")
            time.sleep(2)
            reintentos += 1
            if reintentos >= 5:
                raise RuntimeError(
                    "No se pudieron levantar los servicios de Docker después de 5 intentos."
                )

    match scenario:
        case Scenario.A | Scenario.B:
            try:
                fill_database(1)
            except Exception as exc:
                print(f"[ERROR] No se pudo llenar la base de datos para el escenario {scenario.name}: {exc}")
        case Scenario.C | Scenario.D:
            try:
                fill_database(REQUESTS)
            except Exception as exc:
                print(f"[ERROR] No se pudo llenar la base de datos para el escenario {scenario.name}: {exc}")

    # Esperar a que la aplicación esté disponible.
    await wait_for_api()

    for repetition in range(1, REPETITIONS + 1):
        print()
        print(f"[{scenario.name}] Repetición " f"{repetition}/{REPETITIONS}")

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
        response = await client.get(
            url,
            headers={"API-Key": "apikey_admin"}
        )

        print(
            "[CACHE] status=%s cache=%s"
            % (
                response.status_code,
                response.headers.get(CACHE_HEADER),
            )
        )


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
