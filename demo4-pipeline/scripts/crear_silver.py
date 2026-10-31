"""Crea las tablas Iceberg de silver con Athena. Se puede repetir sin efectos.

Uso:
    python demo4-pipeline/scripts/crear_silver.py [--perfil curso]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import boto3

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from comun import athena  # noqa: E402
from comun.terraform import outputs  # noqa: E402

DDL = RAIZ / "demo4-pipeline" / "sql" / "athena" / "silver.sql"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    tf = outputs("demo3-catalogo-athena/infra")
    cliente = boto3.Session(profile_name=args.perfil, region_name=tf["region"]).client("athena")
    texto = athena.sustituir(DDL.read_text(encoding="utf-8"), {"bucket": tf["bucket_name"]})
    for sentencia in athena.separar_sentencias(texto):
        tabla = sentencia.split("(")[0].split()[-1]
        print(f"Creando {tabla}")
        athena.ejecutar(cliente, sentencia, tf["workgroup"])
    print("Tablas de silver listas.")


if __name__ == "__main__":
    main()
