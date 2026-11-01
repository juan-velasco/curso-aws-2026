"""Genera hallazgos de ejemplo de GuardDuty y los cuenta por severidad.

Cada hallazgo de severidad alta manda un email: sin --tipos, salen muchos.

Uso:
    python ejercicio-g-guardduty-inspector/scripts/hallazgos_ejemplo.py [--perfil curso]
    python ejercicio-g-guardduty-inspector/scripts/hallazgos_ejemplo.py --tipos Backdoor:EC2/C&CActivity.B
    python ejercicio-g-guardduty-inspector/scripts/hallazgos_ejemplo.py --solo-contar
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun.terraform import outputs  # noqa: E402

TRAMOS = ("Crítica", "Alta", "Media", "Baja")


def tramo(severidad: float) -> str:
    """Los tramos de la consola de GuardDuty."""
    if severidad >= 9:
        return "Crítica"
    if severidad >= 7:
        return "Alta"
    if severidad >= 4:
        return "Media"
    return "Baja"


def es_ejemplo(hallazgo: dict) -> bool:
    """La API no pone [SAMPLE] en el título: lo marca sample=true dentro de un JSON en texto."""
    valor = hallazgo.get("Service", {}).get("AdditionalInfo", {}).get("Value") or "{}"
    return json.loads(valor).get("sample") is True


def contar_ejemplos(hallazgos: list[dict]) -> Counter:
    return Counter(tramo(h["Severity"]) for h in hallazgos if es_ejemplo(h))


def leer_hallazgos(gd, detector: str) -> list[dict]:
    paginas = gd.get_paginator("list_findings").paginate(DetectorId=detector)
    ids = [i for pagina in paginas for i in pagina["FindingIds"]]
    hallazgos = []
    for inicio in range(0, len(ids), 50):
        hallazgos += gd.get_findings(DetectorId=detector, FindingIds=ids[inicio : inicio + 50])["Findings"]
    return hallazgos


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    p.add_argument("--tipos", nargs="*", default=[], help="Tipos de hallazgo. Sin indicar, uno de cada tipo")
    p.add_argument("--solo-contar", action="store_true", help="No genera, solo cuenta")
    args = p.parse_args()

    tf = outputs("ejercicio-g-guardduty-inspector/infra")
    sesion = boto3.Session(profile_name=args.perfil, region_name=tf["region"])
    gd = sesion.client("guardduty")
    detectores = gd.list_detectors()["DetectorIds"]
    if not detectores:
        sys.exit("No hay detector de GuardDuty en esta región.")

    if not args.solo_contar:
        gd.create_sample_findings(DetectorId=detectores[0], FindingTypes=args.tipos)
        print("Hallazgos de ejemplo pedidos. Tardan unos segundos en aparecer.")
        time.sleep(20)

    recuento = contar_ejemplos(leer_hallazgos(gd, detectores[0]))
    print(f"Hallazgos de ejemplo: {sum(recuento.values())}")
    for nombre in TRAMOS:
        print(f"  {nombre}: {recuento[nombre]}")


if __name__ == "__main__":
    main()
