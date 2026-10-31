"""Revisa los criterios de aceptación de la demo 3.

Uso:
    python demo3-catalogo-athena/scripts/comprobar_demo3.py [--fecha AAAA-MM-DD] [--perfil curso]
"""

from __future__ import annotations

import argparse
import gzip
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import athena  # noqa: E402
from comun.terraform import outputs  # noqa: E402

# Tipos esperados según el esquema real de DMS (ESTADO_SESION1.md §4.2)
TIPOS_CLIENTES = {
    "op": "string",
    "ts_commit": "string",
    "cliente_id": "string",
    "segmento": "string",
    "fecha_alta": "date",
    "actualizado_en": "timestamp",
}
TIPOS_PRODUCTOS = {
    "ts_commit": "string",
    "producto_id": "string",
    "precio_catalogo": "decimal(8,2)",
    "coste_unitario": "decimal(8,2)",
}

resultados: list[tuple[bool | None, str, str]] = []


def criterio(estado: bool | None, nombre: str, detalle: str = "") -> None:
    resultados.append((estado, nombre, detalle))


def lineas_en_s3(s3, bucket: str, fecha: date) -> int:
    prefijo = f"bronze/ventas/anio={fecha:%Y}/mes={fecha:%m}/dia={fecha:%d}/"
    total = 0
    for pagina in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefijo):
        for o in pagina.get("Contents", []):
            cuerpo = s3.get_object(Bucket=bucket, Key=o["Key"])["Body"].read()
            total += gzip.decompress(cuerpo).count(b"\n")
    return total


def comprobar_tipos(glue, tabla: str, esperados: dict[str, str]) -> None:
    try:
        columnas = glue.get_table(DatabaseName="bronze", Name=tabla)["Table"]["StorageDescriptor"]["Columns"]
    except glue.exceptions.EntityNotFoundException:
        criterio(False, f"Existe bronze.{tabla}", "clientes: sql/04_bronze_clientes.sql; productos: crawler")
        return
    tipos = {c["Name"]: c["Type"] for c in columnas}
    distintos = {k: tipos.get(k) for k, v in esperados.items() if tipos.get(k) != v}
    criterio(not distintos, f"bronze.{tabla} con los tipos de DMS", f"distintos: {distintos}" if distintos else "")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fecha", type=date.fromisoformat, help="día de ventas a comprobar (por defecto, ayer en UTC)")
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    tf = outputs("demo3-catalogo-athena/infra")
    sesion = boto3.Session(profile_name=args.perfil, region_name=tf["region"])
    s3, glue, cliente = sesion.client("s3"), sesion.client("glue"), sesion.client("athena")
    fecha = args.fecha or datetime.now(UTC).date() - timedelta(days=1)
    filtro = f"anio = '{fecha:%Y}' AND mes = '{fecha:%m}' AND dia = '{fecha:%d}'"

    # --- Tablas -------------------------------------------------------------------
    try:
        glue.get_table(DatabaseName="bronze", Name="ventas")
        criterio(True, "Existe bronze.ventas")
    except glue.exceptions.EntityNotFoundException:
        criterio(False, "Existe bronze.ventas", "crea la tabla con sql/01_bronze_ventas.sql")
    comprobar_tipos(glue, "clientes", TIPOS_CLIENTES)
    comprobar_tipos(glue, "productos", TIPOS_PRODUCTOS)

    if resultados[0][0]:
        # --- Lectura de los .json.gz y recuento de un día -------------------------
        en_s3 = lineas_en_s3(s3, tf["bucket_name"], fecha)
        sql = f"SELECT count(*) AS eventos, count(DISTINCT event_id) AS unicos FROM bronze.ventas WHERE {filtro}"
        dia = athena.ejecutar(cliente, sql, tf["workgroup"])
        eventos, unicos = int(dia.primera["eventos"]), int(dia.primera["unicos"])
        criterio(
            en_s3 > 0 and eventos == en_s3,
            f"Athena lee los .json.gz: recuento de {fecha} = líneas en S3",
            f"{eventos} en Athena / {en_s3} en S3",
        )
        criterio(
            eventos > unicos,
            "Duplicados visibles: count(*) > count(DISTINCT event_id)",
            f"{eventos} eventos, {unicos} únicos",
        )

        # --- Coste: particiones ---------------------------------------------------
        todo = athena.ejecutar(cliente, "SELECT count(*) AS eventos FROM bronze.ventas", tf["workgroup"])
        criterio(
            0 < dia.bytes_escaneados < todo.bytes_escaneados / 5,
            "Filtrar por partición escanea mucho menos",
            f"{athena.formato_bytes(dia.bytes_escaneados)} frente a {athena.formato_bytes(todo.bytes_escaneados)}",
        )
        print(f"Total de eventos en bronze.ventas: {todo.primera['eventos']}\n")

    # --- Maestros -----------------------------------------------------------------
    for tabla, minimo in (("clientes", 4003), ("productos", 1200)):
        try:
            consulta = athena.ejecutar(cliente, f"SELECT count(*) AS n FROM bronze.{tabla}", tf["workgroup"])
            filas = int(consulta.primera["n"])
            criterio(filas >= minimo, f"bronze.{tabla} se puede consultar", f"{filas} filas")
        except athena.ErrorAthena as e:
            criterio(False, f"bronze.{tabla} se puede consultar", str(e).splitlines()[0])

    print("Criterios de aceptación")
    for estado, nombre, detalle in resultados:
        texto = {True: "OK", False: "KO", None: "--"}[estado]
        print(f"  [{texto}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    sys.exit(1 if any(r[0] is False for r in resultados) else 0)


if __name__ == "__main__":
    main()
