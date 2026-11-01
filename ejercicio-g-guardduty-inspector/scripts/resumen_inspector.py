"""Espera a los escaneos de Inspector y resume los hallazgos de las dos imágenes.

Uso:
    python ejercicio-g-guardduty-inspector/scripts/resumen_inspector.py [--limite-min 15] [--perfil curso]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun.terraform import outputs  # noqa: E402

IMAGENES = (("api-ventas", "1.0.0"), ("curso-imagen-antigua", "3.8"))
SEVERIDADES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL", "UNTRIAGED")
ESTADOS_TERMINADOS = {"ACTIVE", "COMPLETE", "SCAN_ELIGIBILITY_EXPIRED", "FINDINGS_UNAVAILABLE", "UNSUPPORTED_IMAGE"}


def por_severidad(hallazgos: list[dict]) -> Counter:
    return Counter(h["severity"] for h in hallazgos)


def paquetes_con_mas_cve(hallazgos: list[dict], cuantos: int = 5) -> list[tuple[str, int]]:
    """Paquetes ordenados por CVE distintos, sin contar dos veces una vulnerabilidad."""
    cves: dict[str, set[str]] = defaultdict(set)
    for hallazgo in hallazgos:
        detalle = hallazgo.get("packageVulnerabilityDetails", {})
        for paquete in detalle.get("vulnerablePackages", []):
            cves[paquete["name"]].add(detalle["vulnerabilityId"])
    return sorted(((nombre, len(ids)) for nombre, ids in cves.items()), key=lambda p: (-p[1], p[0]))[:cuantos]


def estado_escaneo(ecr, repositorio: str, etiqueta: str) -> str:
    try:
        detalle = ecr.describe_image_scan_findings(repositoryName=repositorio, imageId={"imageTag": etiqueta})
    except ClientError as e:
        if e.response["Error"]["Code"] == "ScanNotFoundException":
            return "PENDING"
        raise
    return detalle["imageScanStatus"]["status"]


def esperar_escaneos(ecr, limite_min: int) -> None:
    fin = time.monotonic() + limite_min * 60
    pendientes = set(IMAGENES)
    while pendientes:
        for repositorio, etiqueta in sorted(pendientes):
            estado = estado_escaneo(ecr, repositorio, etiqueta)
            print(f"  {repositorio}:{etiqueta}: {estado}")
            if estado in ESTADOS_TERMINADOS:
                pendientes.discard((repositorio, etiqueta))
        if pendientes:
            if time.monotonic() > fin:
                sys.exit(f"Sin terminar tras {limite_min} min: {sorted(pendientes)}. Vuelve a lanzarlo luego.")
            time.sleep(30)


def hallazgos_de_imagen(inspector, repositorio: str, etiqueta: str) -> list[dict]:
    criterios = {
        "ecrImageRepositoryName": [{"comparison": "EQUALS", "value": repositorio}],
        "ecrImageTags": [{"comparison": "EQUALS", "value": etiqueta}],
        "findingStatus": [{"comparison": "EQUALS", "value": "ACTIVE"}],
    }
    paginador = inspector.get_paginator("list_findings")
    return [h for pagina in paginador.paginate(filterCriteria=criterios) for h in pagina["findings"]]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    p.add_argument("--limite-min", type=int, default=15)
    args = p.parse_args()

    tf = outputs("ejercicio-g-guardduty-inspector/infra")
    sesion = boto3.Session(profile_name=args.perfil, region_name=tf["region"])
    esperar_escaneos(sesion.client("ecr"), args.limite_min)

    inspector = sesion.client("inspector2")
    for repositorio, etiqueta in IMAGENES:
        hallazgos = hallazgos_de_imagen(inspector, repositorio, etiqueta)
        recuento = por_severidad(hallazgos)
        print(f"\n{repositorio}:{etiqueta}: {len(hallazgos)} hallazgos")
        print("  " + ", ".join(f"{s}: {recuento[s]}" for s in SEVERIDADES if recuento[s]))
        for nombre, n in paquetes_con_mas_cve(hallazgos):
            print(f"  {nombre}: {n} CVE")


if __name__ == "__main__":
    main()
