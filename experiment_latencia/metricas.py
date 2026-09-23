import csv
from typing import Any

import numpy as np

from experiment_latencia.config import RAW_DIR, RESULTS_DIR
from experiment_latencia.modelos import Scenario
from experiment_latencia.requests import RequestResult

try:
    from scipy.stats import wilcoxon
except ImportError:
    wilcoxon = None


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
