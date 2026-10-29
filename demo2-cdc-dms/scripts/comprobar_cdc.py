"""Comprueba lo que ha dejado DMS en bronze/cdc/ (diapositiva «Qué deja DMS en bronze»).

Uso:
    python demo2-cdc-dms/scripts/comprobar_cdc.py
"""

import io
import sys

import pyarrow.parquet as pq
from conexion import sesion_aws, tf

PREFIJO = "bronze/cdc/public/"
COLUMNAS_CDC = ["Op", "cliente_id", "segmento", "provincia", "ts_commit"]
ESPERADOS = {("U", "C-17"): "Premium", ("I", "C-4001"): "Standard", ("D", "C-981"): None}

resultados: list[tuple[bool, str]] = []


def criterio(ok: bool, texto: str) -> None:
    resultados.append((ok, texto))


def listar(s3, bucket: str, prefijo: str) -> list[dict]:
    objetos = []
    for pagina in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefijo):
        objetos += pagina.get("Contents", [])
    return sorted(objetos, key=lambda o: (o["LastModified"], o["Key"]))


def leer(s3, bucket: str, clave: str):
    return pq.read_table(io.BytesIO(s3.get_object(Bucket=bucket, Key=clave)["Body"].read()))


def es_load(clave: str) -> bool:
    return clave.rsplit("/", 1)[-1].startswith("LOAD")


def main() -> None:
    bucket = tf()["bucket_name"]
    s3 = sesion_aws().client("s3")

    for tabla, filas_esperadas in (("clientes", 4000), ("productos", 1200)):
        objetos = listar(s3, bucket, f"{PREFIJO}{tabla}/")
        print(f"\ns3://{bucket}/{PREFIJO}{tabla}/  ({len(objetos)} ficheros)")
        for o in objetos:
            print(f"  {o['LastModified']:%Y-%m-%d %H:%M:%S}  {o['Size']:>8} B  {o['Key'].removeprefix(PREFIJO)}")

        cargas = [leer(s3, bucket, o["Key"]) for o in objetos if es_load(o["Key"])]
        filas = sum(t.num_rows for t in cargas)
        con_op = any("Op" in t.column_names for t in cargas)
        print(f"  Carga completa (LOAD*): {filas} filas, columnas: {cargas[0].column_names if cargas else '-'}")
        criterio(filas == filas_esperadas and not con_op and bool(cargas),
                 f"LOAD de {tabla} con {filas_esperadas} filas y sin columna Op ({filas} filas, Op: {con_op})")

        if tabla != "clientes":
            continue

        # Ficheros CDC: todo lo que no es LOAD, en carpetas AAAA/MM/DD
        cdc = [o for o in objetos if not es_load(o["Key"])]
        vistos = {}
        for o in cdc:
            t = leer(s3, bucket, o["Key"])
            print(f"\n  CDC {o['Key'].removeprefix(PREFIJO)}  ({t.num_rows} filas)")
            columnas = [c for c in COLUMNAS_CDC if c in t.column_names]
            for fila in t.select(columnas).to_pylist():
                print("   ", "  ".join(f"{c}={fila[c]}" for c in columnas))
                vistos[(fila.get("Op"), fila.get("cliente_id"))] = fila
        if not cdc:
            print("\n  Aún no hay ficheros CDC (aparecen ~1 minuto después de aplicar_cambios.py)")
        en_fecha = all(len(o["Key"].removeprefix(f"{PREFIJO}clientes/").split("/")) == 4 for o in cdc)
        criterio(bool(cdc) and en_fecha, "Ficheros CDC de clientes en carpetas AAAA/MM/DD/")
        for (op, cliente_id), segmento in ESPERADOS.items():
            fila = vistos.get((op, cliente_id))
            ok = fila is not None and fila.get("ts_commit") is not None
            if ok and segmento:
                ok = fila.get("segmento") == segmento
            criterio(ok, f"{op} de {cliente_id}" + (f" ({segmento})" if segmento else "") + " con ts_commit")

    print("\nCriterios de aceptación")
    for ok, texto in resultados:
        print(f"  [{'OK' if ok else 'KO'}] {texto}")
    sys.exit(0 if all(ok for ok, _ in resultados) else 1)


if __name__ == "__main__":
    main()
