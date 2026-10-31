"""Revisa los criterios de aceptación de la demo 4 que se pueden consultar.

Los correos de SNS y las ejecuciones con fallo forzado o sin datos se comprueban
con ejecutar_pipeline.py y en el buzón.

Uso:
    python demo4-pipeline/scripts/comprobar_demo4.py [--perfil curso]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import athena, redshift  # noqa: E402
from comun.terraform import outputs  # noqa: E402

resultados: list[tuple[bool, str, str]] = []


def criterio(estado: bool, nombre: str, detalle: str = "") -> None:
    resultados.append((estado, nombre, detalle))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    tf = outputs("demo4-pipeline/infra")
    wg = outputs("demo3-catalogo-athena/infra")["workgroup"]
    sesion = boto3.Session(profile_name=args.perfil, region_name=tf["region"])
    cliente_athena, datos, s3 = sesion.client("athena"), sesion.client("redshift-data"), sesion.client("s3")

    def en_athena(sql: str) -> dict:
        return athena.ejecutar(cliente_athena, sql, wg).primera

    def en_redshift(sql: str) -> list[list]:
        return redshift.ejecutar(datos, sql, tf["redshift_workgroup"], tf["secreto_admin_arn"])[1]

    # --- Silver: ventas ---------------------------------------------------------------
    v = en_athena("SELECT count(*) AS filas, count(DISTINCT event_id) AS unicos FROM silver.ventas")
    filas = int(v["filas"])
    criterio(filas > 0 and v["filas"] == v["unicos"], "silver.ventas sin duplicados", f"{v['filas']} / {v['unicos']}")

    b = en_athena("SELECT count(*) AS filas, count(DISTINCT event_id) AS unicos FROM bronze.ventas")
    criterio(int(b["filas"]) > int(b["unicos"]), "bronze.ventas tiene duplicados", f"{b['filas']} / {b['unicos']}")
    criterio(
        int(b["unicos"]) == filas,
        "Todos los eventos de bronze están en silver",
        f"{b['unicos']} únicos en bronze / {filas} en silver",
    )

    jpy = en_athena(
        "SELECT count(*) AS n, count_if(importe_bruto <> DECIMAL '39.95') AS mal FROM silver.ventas "
        "WHERE moneda = 'JPY' AND unidades = 1 AND precio_unitario = DECIMAL '6392.00'"
    )
    criterio(jpy["mal"] == "0" and jpy["n"] != "0", "Un JPY de 6.392 son 39,95 EUR", f"{jpy['n']} líneas")

    pais = en_athena("SELECT count_if(pais NOT IN ('ES', 'FR', 'US', 'JP', 'CN')) AS mal FROM silver.ventas")
    criterio(pais["mal"] == "0", "pais correcto, también en online", f"{pais['mal']} incorrectos")

    # --- Silver: dimensiones ----------------------------------------------------------------
    versiones = athena.ejecutar(
        cliente_athena,
        "SELECT cliente_id, segmento, CAST(valid_from AS varchar) AS d, CAST(valid_to AS varchar) AS h, es_baja "
        "FROM silver.dim_cliente WHERE cliente_id IN ('C-17', 'C-4001', 'C-981') ORDER BY 1, 3",
        wg,
    ).filas
    criterio(
        versiones
        == [
            ["C-17", "Standard", "1900-01-01", "2026-10-28", "false"],
            ["C-17", "Premium", "2026-10-28", "9999-12-31", "false"],
            ["C-4001", "Standard", "2026-10-28", "9999-12-31", "false"],
            ["C-981", "Standard", "1900-01-01", "2026-10-28", "true"],
        ],
        "SCD2: C-17 con dos versiones, C-4001 desde el 28-10 y C-981 cerrado",
        str(versiones) if len(versiones) != 4 else "",
    )

    # --- Control -------------------------------------------------------------------------------
    cuerpo = s3.get_object(Bucket=tf["bucket_name"], Key="control/calidad/ventas/ultima.json")["Body"].read()
    control = json.loads(cuerpo)
    criterio(
        {"filas_leidas", "filas_ok", "filas_cuarentena", "pct_cuarentena", "reglas", "ts_fin"} <= set(control),
        "Control de calidad completo",
        f"última ejecución: {control['filas_leidas']} leídas, {control['pct_cuarentena']} % en cuarentena",
    )

    # --- Gold ------------------------------------------------------------------------------------
    gold = int(en_redshift("SELECT COUNT(*) FROM gold.fct_ventas")[0][0])
    criterio(gold == filas, "gold.fct_ventas cuadra con silver.ventas", f"{gold} / {filas}")

    sin_cliente_silver = int(en_athena("SELECT count_if(cliente_id IS NULL) AS n FROM silver.ventas")["n"])
    sin_cliente_gold = int(en_redshift("SELECT COUNT(*) FROM gold.fct_ventas WHERE cliente_sk = -1")[0][0])
    criterio(
        sin_cliente_gold >= sin_cliente_silver > 0,
        "Las ventas sin cliente apuntan a cliente_sk = -1",
        f"{sin_cliente_gold} en gold; {sin_cliente_silver} sin cliente en silver (el resto: ventas tras una baja)",
    )

    for vista in ("mv_ventas_diarias", "v_dashboard_ventas"):
        n = int(en_redshift(f"SELECT COUNT(*) FROM gold.{vista}")[0][0])
        criterio(n > 0, f"gold.{vista} devuelve datos", f"{n} filas")

    print("Criterios de aceptación")
    for estado, nombre, detalle in resultados:
        print(f"  [{'OK' if estado else 'KO'}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    sys.exit(0 if all(r[0] for r in resultados) else 1)


if __name__ == "__main__":
    main()
