"""Revisa los criterios de aceptación de la demo 6 que se pueden consultar.

Uso:
    python demo6-prevision-sagemaker/scripts/comprobar_demo6.py [--perfil curso]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import redshift  # noqa: E402
from comun.terraform import outputs  # noqa: E402

PREFIJOS = ("ml/ventas_diarias/", "ml/calendario/", "ml/clima/", "ml/predicciones/")
DIAS_POR_SERIE = 28

resultados: list[tuple[bool, str, str]] = []


def criterio(estado: bool, nombre: str, detalle: str = "") -> None:
    resultados.append((estado, nombre, detalle))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    gold = outputs("demo4-pipeline/infra")
    tf = outputs("demo6-prevision-sagemaker/infra")
    sesion = boto3.Session(profile_name=args.perfil, region_name=tf["region"])
    s3, sm = sesion.client("s3"), sesion.client("sagemaker")
    datos = sesion.client("redshift-data")

    def en_redshift(sql: str) -> list[list]:
        return redshift.ejecutar(datos, sql, gold["redshift_workgroup"], gold["secreto_admin_arn"])[1]

    for prefijo in PREFIJOS:
        n = s3.list_objects_v2(Bucket=tf["bucket_name"], Prefix=prefijo).get("KeyCount", 0)
        criterio(n > 0, f"Ficheros en {prefijo}", f"{n}")

    series = en_redshift(
        "SELECT COUNT(*), COALESCE(MIN(dias), 0), COALESCE(MAX(dias), 0) FROM ("
        "  SELECT pais, familia, COUNT(DISTINCT fecha_sk) AS dias FROM gold.fct_prevision"
        "  WHERE fecha_calculo = (SELECT MAX(fecha_calculo) FROM gold.fct_prevision)"
        "  GROUP BY 1, 2)"
    )[0]
    n_series, minimo, maximo = int(series[0]), int(series[1]), int(series[2])
    criterio(
        n_series > 0 and minimo == maximo == DIAS_POR_SERIE,
        "gold.fct_prevision con 28 días por serie",
        f"{n_series} series, {n_series * maximo} filas",
    )
    vista = int(en_redshift("SELECT COUNT(*) FROM gold.v_prevision_vs_real")[0][0])
    criterio(vista > 0, "gold.v_prevision_vs_real devuelve filas", f"{vista}")

    endpoints = sm.list_endpoints()["Endpoints"]
    criterio(not endpoints, "Ningún endpoint", ", ".join(e["EndpointName"] for e in endpoints))
    apps = [
        a["AppName"]
        for pagina in sm.get_paginator("list_apps").paginate(DomainIdEquals=tf["dominio_id"])
        for a in pagina["Apps"]
        if a["Status"] == "InService"
    ]
    criterio(not apps, "Ninguna app de Studio en InService", ", ".join(apps))
    entrenando = sm.list_training_jobs(StatusEquals="InProgress")["TrainingJobSummaries"]
    criterio(not entrenando, "Ningún training job en curso")
    transformando = sm.list_transform_jobs(StatusEquals="InProgress")["TransformJobSummaries"]
    criterio(not transformando, "Ningún batch transform en curso")

    print("Criterios de aceptación")
    for estado, nombre, detalle in resultados:
        print(f"  [{'OK' if estado else 'FALLO'}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    if not all(estado for estado, _, _ in resultados):
        sys.exit(1)


if __name__ == "__main__":
    main()
