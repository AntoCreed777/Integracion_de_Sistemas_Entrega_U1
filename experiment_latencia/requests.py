import asyncio
import time
from dataclasses import dataclass

import httpx

from experiment_latencia.config import (
    BASE_URL,
    CACHE_HEADER,
    ENDPOINT,
    HTTP_TIMEOUT,
    WARMUP_REQUESTS,
    WORKERS,
)


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
        url = url.lstrip("/") + "/" + str(resource_id)

    return url


async def fetch(
    client: httpx.AsyncClient,
    url: str,
    request_id: int,
) -> RequestResult:
    start = time.perf_counter()

    try:
        response = await client.get(
            url,
            headers={"API-Key": "apikey_admin"}
        )

        if response.status_code != 200:
            print(f"[ERROR] request_id={request_id} status_code={response.status_code}")
            print(response.text)

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
