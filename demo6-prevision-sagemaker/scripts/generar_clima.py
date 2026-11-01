"""Genera un clima INVENTADO por país y día y lo sube a s3://<bucket>/ml/clima/.

El histórico de ventas no tiene efecto del clima: estas columnas no deberían mejorar el modelo.
Es determinista: cada país y día tienen su semilla, así que ampliar el rango no cambia lo ya generado.
Cubre desde el primer día de gold.mv_ventas_diarias hasta 28 días después del último.

Uso:
    python demo6-prevision-sagemaker/scripts/generar_clima.py [--perfil curso]
"""

from __future__ import annotations

import argparse
import io
import math
import os
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import boto3
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import redshift  # noqa: E402
from comun.terraform import outputs  # noqa: E402

HORIZONTE_DIAS = 28
DIA_MAS_CALIDO = 200  # mediados de julio; los cinco países están en el hemisferio norte

# País -> (temperatura media anual, amplitud estacional, probabilidad de lluvia, lluvia media en mm)
PERFILES = {
    "ES": (16.0, 8.0, 0.20, 5.0),
    "FR": (12.0, 8.0, 0.35, 5.0),
    "US": (13.0, 11.0, 0.30, 7.0),
    "JP": (16.0, 10.0, 0.35, 9.0),
    "CN": (17.0, 12.0, 0.30, 8.0),
}


def fila(pais: str, dia: date) -> dict:
    media, amplitud, prob_lluvia, lluvia_media = PERFILES[pais]
    azar = random.Random(f"clima-{pais}-{dia.isoformat()}")
    estacion = math.cos(2 * math.pi * (dia.timetuple().tm_yday - DIA_MAS_CALIDO) / 365)
    llueve = azar.random() < prob_lluvia
    return {
        "fecha_sk": int(dia.strftime("%Y%m%d")),
        "pais": pais,
        "temp_media": round(media + amplitud * estacion + azar.gauss(0, 2), 1),
        "lluvia_mm": round(azar.expovariate(1 / lluvia_media), 1) if llueve else 0.0,
    }


def generar(inicio: date, fin: date) -> list[dict]:
    dias = (fin - inicio).days + 1
    return [fila(pais, inicio + timedelta(days=n)) for pais in PERFILES for n in range(dias)]


def a_parquet(filas: list[dict]) -> bytes:
    esquema = pa.schema(
        [("fecha_sk", pa.int32()), ("pais", pa.string()), ("temp_media", pa.float64()), ("lluvia_mm", pa.float64())]
    )
    salida = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(filas, schema=esquema), salida)
    return salida.getvalue()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    tf = outputs("demo4-pipeline/infra")
    sesion = boto3.Session(profile_name=args.perfil, region_name=tf["region"])
    primera, ultima = redshift.ejecutar(
        sesion.client("redshift-data"),
        "SELECT MIN(fecha_sk), MAX(fecha_sk) FROM gold.mv_ventas_diarias",
        tf["redshift_workgroup"],
        tf["secreto_admin_arn"],
    )[1][0]
    inicio = datetime.strptime(str(primera), "%Y%m%d").date()
    fin = datetime.strptime(str(ultima), "%Y%m%d").date() + timedelta(days=HORIZONTE_DIAS)

    filas = generar(inicio, fin)
    clave = "ml/clima/clima.parquet"
    sesion.client("s3").put_object(Bucket=tf["bucket_name"], Key=clave, Body=a_parquet(filas))
    print(f"Clima inventado: {len(filas)} filas, de {inicio} a {fin}, en s3://{tf['bucket_name']}/{clave}")


if __name__ == "__main__":
    main()
