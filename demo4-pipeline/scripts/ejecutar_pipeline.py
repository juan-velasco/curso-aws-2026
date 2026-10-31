"""Lanza la máquina de estados del pipeline y sigue su estado hasta que termina.

Uso:
    python demo4-pipeline/scripts/ejecutar_pipeline.py [--forzar-fallo] [--perfil curso]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun.terraform import outputs  # noqa: E402

ESPERA_S = 10


def estados_recorridos(sfn, arn: str) -> list[str]:
    paginas = sfn.get_paginator("get_execution_history").paginate(executionArn=arn)
    eventos = [e for pagina in paginas for e in pagina["events"]]
    return [e["stateEnteredEventDetails"]["name"] for e in eventos if "stateEnteredEventDetails" in e]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--forzar-fallo", action="store_true", help="hace fallar los jobs para ver la rama de error")
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    tf = outputs("demo4-pipeline/infra")
    sfn = boto3.Session(profile_name=args.perfil, region_name=tf["region"]).client("stepfunctions")
    entrada = {"forzar_fallo": "true" if args.forzar_fallo else "false"}
    arn = sfn.start_execution(stateMachineArn=tf["maquina_arn"], input=json.dumps(entrada))["executionArn"]
    print(f"Ejecución: {arn}\nEntrada: {entrada}")

    vistos = 0
    while True:
        estado = sfn.describe_execution(executionArn=arn)["status"]
        recorridos = estados_recorridos(sfn, arn)
        for nombre in recorridos[vistos:]:
            print(f"  -> {nombre}")
        vistos = len(recorridos)
        if estado != "RUNNING":
            break
        time.sleep(ESPERA_S)
    print(f"Resultado: {estado}")
    sys.exit(0 if estado == "SUCCEEDED" else 1)


if __name__ == "__main__":
    main()
