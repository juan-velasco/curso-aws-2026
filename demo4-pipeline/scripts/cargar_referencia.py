"""Carga tiendas, tipos de cambio y calendario en silver con Athena, desde comun/.

Es idempotente: vacía cada tabla antes de cargarla.

Uso:
    python demo4-pipeline/scripts/cargar_referencia.py [--perfil curso]
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import athena, maestros, referencia  # noqa: E402
from comun.terraform import outputs  # noqa: E402

TAM_LOTE = 500


def literal(valor) -> str:
    """Un valor de Python como literal de SQL de Athena."""
    if valor is None:
        return "NULL"
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, date):
        return f"DATE '{valor}'"
    if isinstance(valor, Decimal):
        return f"DECIMAL '{valor}'"
    if isinstance(valor, int):
        return str(valor)
    return "'" + str(valor).replace("'", "''") + "'"


def inserts(tabla: str, filas: list[tuple]) -> Iterable[str]:
    """Sentencias INSERT INTO ... VALUES por lotes."""
    for inicio in range(0, len(filas), TAM_LOTE):
        lote = filas[inicio : inicio + TAM_LOTE]
        valores = ",\n".join("(" + ", ".join(literal(v) for v in fila) + ")" for fila in lote)
        yield f"INSERT INTO silver.{tabla} VALUES\n{valores}"


def filas_tiendas() -> list[tuple]:
    return [
        (t.tienda_id, t.nombre, t.pais, t.region, t.ciudad, t.formato, t.superficie_m2, t.es_online, t.moneda)
        for t in maestros.tiendas()
    ]


def filas_tipos_cambio() -> list[tuple]:
    return [(t["moneda"], t["eur_por_unidad"]) for t in referencia.tipos_cambio()]


def filas_calendario() -> list[tuple]:
    return [tuple(referencia.como_dict(d).values()) for d in referencia.calendario()]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    tf = outputs("demo3-catalogo-athena/infra")
    cliente = boto3.Session(profile_name=args.perfil, region_name=tf["region"]).client("athena")
    for tabla, filas in (
        ("tiendas", filas_tiendas()),
        ("tipos_cambio", filas_tipos_cambio()),
        ("calendario", filas_calendario()),
    ):
        athena.ejecutar(cliente, f"DELETE FROM silver.{tabla}", tf["workgroup"])
        for sentencia in inserts(tabla, filas):
            athena.ejecutar(cliente, sentencia, tf["workgroup"])
        contadas = athena.ejecutar(cliente, f"SELECT count(*) AS n FROM silver.{tabla}", tf["workgroup"]).primera["n"]
        print(f"silver.{tabla}: {contadas} filas")
        if int(contadas) != len(filas):
            sys.exit(f"Se esperaban {len(filas)} filas en silver.{tabla}")


if __name__ == "__main__":
    main()
