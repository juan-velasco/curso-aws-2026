"""Carga gold con la ventana completa del histórico.

La máquina de estados solo recarga ayer y hoy, así que la primera vez hace falta
esta carga. La ventana va del primer día de silver.ventas a mañana.

Uso:
    python demo4-pipeline/scripts/cargar_gold_inicial.py [--perfil curso]
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


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    tf = outputs("demo4-pipeline/infra")
    datos = boto3.Session(profile_name=args.perfil, region_name=tf["region"]).client("redshift-data")

    def consulta(sql: str):
        return redshift.ejecutar(datos, sql, tf["redshift_workgroup"], tf["secreto_admin_arn"])[1]

    desde = consulta("SELECT MIN(fecha_venta)::DATE FROM silver.ventas")[0][0]
    if desde is None:
        sys.exit("silver.ventas está vacía: ejecuta antes los jobs de Glue.")
    print(f"Cargando gold desde {desde}...")
    consulta(f"CALL gold.sp_cargar_gold('{desde}'::TIMESTAMP, (CURRENT_DATE + 1)::TIMESTAMP)")
    consulta("REFRESH MATERIALIZED VIEW gold.mv_ventas_diarias")
    print(f"gold.fct_ventas: {consulta('SELECT COUNT(*) FROM gold.fct_ventas')[0][0]} filas")


if __name__ == "__main__":
    main()
