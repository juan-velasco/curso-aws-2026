"""Refresca la vista, crea gold.fct_prevision y gold.v_prevision_vs_real y lanza los UNLOAD. Se puede repetir.

Uso:
    python demo6-prevision-sagemaker/scripts/preparar_datos.py [--perfil curso]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import boto3

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from comun import athena, redshift  # noqa: E402
from comun.terraform import outputs  # noqa: E402

DIR_SQL = RAIZ / "demo6-prevision-sagemaker" / "sql"
FICHEROS = ("fct_prevision.sql", "v_prevision_vs_real.sql", "unload.sql")
PREFIJOS = ("ml/ventas_diarias/", "ml/calendario/")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    tf = outputs("demo4-pipeline/infra")
    sesion = boto3.Session(profile_name=args.perfil, region_name=tf["region"])
    datos, s3 = sesion.client("redshift-data"), sesion.client("s3")

    # Se refresca sola, pero con retraso: el UNLOAD y el clima deben ver hasta el último día
    redshift.ejecutar(
        datos, "REFRESH MATERIALIZED VIEW gold.mv_ventas_diarias", tf["redshift_workgroup"], tf["secreto_admin_arn"]
    )
    for nombre in FICHEROS:
        print(nombre)
        texto = athena.sustituir((DIR_SQL / nombre).read_text(encoding="utf-8"), {"bucket": tf["bucket_name"]})
        for sentencia in athena.separar_sentencias(texto):
            redshift.ejecutar(datos, sentencia, tf["redshift_workgroup"], tf["secreto_admin_arn"])

    for prefijo in PREFIJOS:
        objetos = s3.list_objects_v2(Bucket=tf["bucket_name"], Prefix=prefijo).get("Contents", [])
        if not objetos:
            sys.exit(f"El UNLOAD no ha dejado ficheros en {prefijo}")
        print(f"  {prefijo}: {len(objetos)} ficheros, {sum(o['Size'] for o in objetos) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
