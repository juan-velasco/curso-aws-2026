"""Ejecuta un fichero SQL o una consulta en el workgroup de Athena del curso.

Muestra las filas y los bytes escaneados de cada sentencia. Sustituye ${bucket}
y, con --fecha, ${fecha_anio}, ${fecha_mes} y ${fecha_dia}.

Uso:
    python demo3-catalogo-athena/scripts/athena.py --fichero demo3-catalogo-athena/sql/01_bronze_ventas.sql
    python demo3-catalogo-athena/scripts/athena.py --fichero demo3-catalogo-athena/sql/02_exploracion.sql --fecha 2026-10-28
    python demo3-catalogo-athena/scripts/athena.py --sql "SELECT count(*) FROM bronze.ventas"
"""  # noqa: E501

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import athena  # noqa: E402
from comun.terraform import outputs  # noqa: E402

MAX_FILAS = 50


def mostrar(resultado: athena.Resultado) -> None:
    if resultado.columnas:
        filas = [resultado.columnas] + [["" if v is None else v for v in f] for f in resultado.filas[:MAX_FILAS]]
        anchos = [max(len(f[i]) for f in filas) for i in range(len(resultado.columnas))]
        for fila in filas:
            print("  " + "  ".join(v.ljust(a) for v, a in zip(fila, anchos)))
        if len(resultado.filas) > MAX_FILAS:
            print(f"  ... y {len(resultado.filas) - MAX_FILAS} filas más")
        print(f"  {len(resultado.filas)} filas")
    print(
        f"  Datos escaneados: {athena.formato_bytes(resultado.bytes_escaneados)} "
        f"(≈ {resultado.coste_usd:.6f} USD)\n"
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    origen = p.add_mutually_exclusive_group(required=True)
    origen.add_argument("--fichero", type=Path, help="fichero SQL con una o varias sentencias")
    origen.add_argument("--sql", help="una sentencia SQL")
    p.add_argument("--fecha", type=date.fromisoformat, help="fecha AAAA-MM-DD para los marcadores ${fecha_*}")
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    tf = outputs("demo3-catalogo-athena/infra")
    valores = {"bucket": tf["bucket_name"]}
    if args.fecha:
        valores |= {
            "fecha_anio": f"{args.fecha:%Y}",
            "fecha_mes": f"{args.fecha:%m}",
            "fecha_dia": f"{args.fecha:%d}",
        }
    texto = args.fichero.read_text(encoding="utf-8") if args.fichero else args.sql
    cliente = boto3.Session(profile_name=args.perfil, region_name=tf["region"]).client("athena")

    for sentencia in athena.separar_sentencias(athena.sustituir(texto, valores)):
        print(sentencia + "\n")
        try:
            mostrar(athena.ejecutar(cliente, sentencia, tf["workgroup"]))
        except athena.ErrorAthena as e:
            sys.exit(str(e))


if __name__ == "__main__":
    main()
