"""Carga la previsión de S3 en gold.fct_prevision y refresca el dataset de QuickSight. Se puede repetir.

Borra esa fecha de cálculo y lanza el COPY. Por defecto, la fecha de cálculo más reciente en S3.

Uso:
    python demo6-prevision-sagemaker/scripts/cargar_prevision.py [--fecha-calculo 2026-11-01] [--perfil curso]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
import uuid
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import redshift  # noqa: E402
from comun.terraform import outputs  # noqa: E402

PREFIJO = "ml/predicciones/"


def fecha_mas_reciente(s3, bucket: str) -> str:
    pagina = s3.list_objects_v2(Bucket=bucket, Prefix=f"{PREFIJO}fecha_calculo=", Delimiter="/")
    carpetas = [c["Prefix"] for c in pagina.get("CommonPrefixes", [])]
    fechas = sorted(re.search(r"fecha_calculo=([\d-]+)/", carpeta).group(1) for carpeta in carpetas)
    if not fechas:
        sys.exit(f"No hay previsiones en s3://{bucket}/{PREFIJO}: ejecuta antes el notebook.")
    return fechas[-1]


def refrescar_quicksight(sesion, dataset: str) -> None:
    qs = sesion.client("quicksight")
    cuenta = sesion.client("sts").get_caller_identity()["Account"]
    id_ingesta = str(uuid.uuid4())
    qs.create_ingestion(AwsAccountId=cuenta, DataSetId=dataset, IngestionId=id_ingesta)
    while True:
        ingesta = qs.describe_ingestion(AwsAccountId=cuenta, DataSetId=dataset, IngestionId=id_ingesta)["Ingestion"]
        if ingesta["IngestionStatus"] in {"COMPLETED", "FAILED", "CANCELLED"}:
            break
        time.sleep(5)
    if ingesta["IngestionStatus"] != "COMPLETED":
        sys.exit(f"Falló el refresco de {dataset}: {ingesta.get('ErrorInfo')}")
    print(f"Dataset {dataset} refrescado: {ingesta['RowInfo']['RowsIngested']} filas.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    p.add_argument("--fecha-calculo", help="AAAA-MM-DD. Por defecto, la más reciente en S3")
    args = p.parse_args()

    tf = outputs("demo4-pipeline/infra")
    sesion = boto3.Session(profile_name=args.perfil, region_name=tf["region"])
    datos = sesion.client("redshift-data")
    fecha = args.fecha_calculo or fecha_mas_reciente(sesion.client("s3"), tf["bucket_name"])

    def en_redshift(sql: str) -> list[list]:
        return redshift.ejecutar(datos, sql, tf["redshift_workgroup"], tf["secreto_admin_arn"])[1]

    en_redshift(f"DELETE FROM gold.fct_prevision WHERE fecha_calculo = '{fecha}'")
    en_redshift(
        "COPY gold.fct_prevision (fecha_calculo, fecha_sk, pais, familia, unidades_previstas) "
        f"FROM 's3://{tf['bucket_name']}/{PREFIJO}fecha_calculo={fecha}/' "
        "IAM_ROLE default CSV IGNOREHEADER 1"
    )
    filas = en_redshift(f"SELECT COUNT(*) FROM gold.fct_prevision WHERE fecha_calculo = '{fecha}'")[0][0]
    print(f"gold.fct_prevision: {filas} filas con fecha de cálculo {fecha}.")

    dataset = outputs("demo6-prevision-sagemaker/infra").get("quicksight_dataset_id")
    if dataset:
        refrescar_quicksight(sesion, dataset)


if __name__ == "__main__":
    main()
