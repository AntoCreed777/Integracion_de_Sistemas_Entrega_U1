import argparse
import asyncio
import pathlib
import sys

from dotenv import load_dotenv

sys.path.append(str(pathlib.Path(__file__).parent.parent.resolve()))
sys.path.append(str(pathlib.Path(__file__).parent.parent.resolve() / "arriendo"))
sys.path.append(str(pathlib.Path(__file__).parent.parent.resolve() / "Equipos"))
sys.path.append(str(pathlib.Path(__file__).parent.parent.resolve() / "experiment_latencia"))


from experiment_latencia.config import RAW_DIR, RESULTS_DIR
from experiment_latencia.metricas import generate_statistical_analysis

load_dotenv()

from experiment_latencia.docker_aux import detener_docker_compose
from experiment_latencia.escenarios import execute_scenario
from experiment_latencia.modelos import Scenario

# ---------------------------------------------------------------------------
# Ejecuciones
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
        except Exception as exc:
            print(f"[ERROR] Al ejecutar el escenario {scenario.name}: {exc}")
        finally:
            detener_docker_compose(delete_volumes=False)

    generate_statistical_analysis()


async def run_one(scenario: Scenario):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        await execute_scenario(scenario)
    except Exception as exc:
        print(f"[ERROR] Al ejecutar el escenario {scenario.name}: {exc}")
    finally:
        detener_docker_compose(delete_volumes=True)

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

    args = parser.parse_args()

    if args.scenario == Scenario.ALL:
        asyncio.run(run_all())
    else:
        asyncio.run(run_one(args.scenario))


if __name__ == "__main__":
    main()
