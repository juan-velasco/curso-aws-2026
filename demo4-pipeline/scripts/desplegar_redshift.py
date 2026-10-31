"""Despliega el SQL de gold en Redshift Serverless con la Data API. Se puede repetir.

Ejecuta sql/redshift/ en orden con el usuario administrador, cuya contraseña
guarda Redshift en Secrets Manager. Las sentencias que crean algo que ya existe
(usuario, rol, política de RLS) no paran el despliegue.

Uso:
    python demo4-pipeline/scripts/desplegar_redshift.py [--perfil curso]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import boto3

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from comun import athena, redshift  # noqa: E402
from comun.terraform import outputs  # noqa: E402

DIR_SQL = RAIZ / "demo4-pipeline" / "sql" / "redshift"
YA_EXISTE = ("already exists", "already attached", "already has", "is already")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    tf = outputs("demo4-pipeline/infra")
    sesion = boto3.Session(profile_name=args.perfil, region_name=tf["region"])
    datos = sesion.client("redshift-data")
    secreto_ro = sesion.client("secretsmanager").get_secret_value(SecretId=tf["secreto_quicksight_ro"])
    valores = {
        "password_quicksight_ro": json.loads(secreto_ro["SecretString"])["password"],
        "rol_pipeline": tf["rol_pipeline"],
    }

    for fichero in sorted(DIR_SQL.glob("*.sql")):
        print(fichero.name)
        texto = athena.sustituir(fichero.read_text(encoding="utf-8"), valores)
        for sentencia in athena.separar_sentencias(texto):
            try:
                redshift.ejecutar(datos, sentencia, tf["redshift_workgroup"], tf["secreto_admin_arn"])
            except redshift.ErrorRedshift as e:
                if not any(frase in str(e) for frase in YA_EXISTE):
                    # No se muestra la sentencia: puede llevar la contraseña de quicksight_ro
                    sys.exit(f"Error en {fichero.name}: {e}")
                print(f"  ya existe: {str(e).splitlines()[0]}")
    print("Gold desplegado.")


if __name__ == "__main__":
    main()
