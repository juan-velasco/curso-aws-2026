"""Comprueba lo que ha llegado a bronze tras una ejecución del generador.

Sustituye a `aws s3 ls | tail`, `gunzip`, `head` y `jq` de la diapositiva
(no existen por defecto en Windows) y revisa los criterios de aceptación.

Uso:
    python demo1-ingesta/scripts/comprobar_bronze.py [--fecha AAAA-MM-DD] [--perfil curso]
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import statistics
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun.terraform import outputs  # noqa: E402

RESUMEN = Path(__file__).resolve().parents[1] / "salida" / "resumen.json"
PATRON_CLAVE = re.compile(r"bronze/ventas/anio=\d{4}/mes=\d{2}/dia=\d{2}/[^/]+\.json\.gz")

resultados: list[tuple[str, str, str]] = []  # (estado, criterio, detalle)


def criterio(estado: bool | None, nombre: str, detalle: str = "") -> None:
    texto = {True: "OK", False: "KO", None: "--"}[estado]
    resultados.append((texto, nombre, detalle))


def parse_ts(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def listar(s3, bucket: str, prefijo: str) -> list[dict]:
    objetos = []
    for pagina in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefijo):
        objetos += pagina.get("Contents", [])
    return sorted(objetos, key=lambda o: o["Key"])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fecha", help="fecha de llegada AAAA-MM-DD (por defecto, hoy en UTC)")
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    p.add_argument("--muestra", type=int, default=3, help="eventos a mostrar del último fichero")
    args = p.parse_args()

    tf = outputs("demo1-ingesta/infra")
    bucket, stream, region = tf["bucket_name"], tf["stream_name"], tf["region"]
    sesion = boto3.Session(profile_name=args.perfil, region_name=region)
    s3 = sesion.client("s3")

    fecha = datetime.strptime(args.fecha, "%Y-%m-%d") if args.fecha else datetime.now(UTC)
    prefijo = f"bronze/ventas/anio={fecha:%Y}/mes={fecha:%m}/dia={fecha:%d}/"
    print(f"Bucket: s3://{bucket}\nPrefijo: {prefijo}\n")

    # --- Ficheros de bronze ---------------------------------------------------
    objetos = listar(s3, bucket, prefijo)
    print(f"{len(objetos)} ficheros. Últimos 5:")
    for o in objetos[-5:]:
        print(f"  {o['LastModified']:%H:%M:%S}  {o['Size']:>8} B  {o['Key']}")
    if not objetos:
        criterio(False, "Hay ficheros en bronze para la fecha", prefijo)

    resumen = json.loads(RESUMEN.read_text(encoding="utf-8")) if RESUMEN.exists() else None
    if resumen is None:
        print(f"\nAviso: no existe {RESUMEN}; no se puede comparar con el generador.")

    eventos, mal_formados, ultimo = [], [], []
    for o in objetos:
        cuerpo = s3.get_object(Bucket=bucket, Key=o["Key"])["Body"].read()
        try:
            lineas = gzip.decompress(cuerpo).decode("utf-8").splitlines()
            fichero = [json.loads(linea) for linea in lineas if linea.strip()]
        except (OSError, ValueError) as e:
            mal_formados.append(f"{o['Key']}: {e}")
            continue
        eventos += fichero
        ultimo = fichero

    if objetos:
        estructura = all(PATRON_CLAVE.fullmatch(o["Key"]) for o in objetos)
        criterio(
            estructura and not mal_formados,
            "Estructura anio=/mes=/dia= con ficheros .json.gz en JSON Lines",
            "; ".join(mal_formados[:3]) or f"{len(objetos)} ficheros",
        )

    if ultimo:
        print(f"\nPrimeros {args.muestra} eventos del último fichero:")
        for e in ultimo[: args.muestra]:
            print(json.dumps(e, indent=2, ensure_ascii=False))

    # --- Comparación con el resumen del generador -------------------------------
    if resumen and objetos:
        inicio = parse_ts(resumen["inicio"]) - timedelta(seconds=1)
        fin = parse_ts(resumen["fin"]) + timedelta(seconds=1)
        de_la_ejecucion = [e for e in eventos if inicio <= parse_ts(e["event_ts"]) <= fin]
        distintos = len({e["event_id"] for e in de_la_ejecucion})
        aceptados = resumen["eventos_aceptados"]
        esperados_distintos = aceptados - resumen["duplicados_aceptados"]
        print(
            f"\nEjecución {resumen['inicio']} -> {resumen['fin']}\n"
            f"  Generador: {aceptados} aceptados por la API ({resumen['duplicados_aceptados']} duplicados)\n"
            f"  Bronze:    {len(de_la_ejecucion)} líneas, {distintos} event_id distintos"
        )
        criterio(
            len(de_la_ejecucion) == aceptados and distintos == esperados_distintos,
            "Líneas en bronze = eventos aceptados por la API",
            f"{len(de_la_ejecucion)} líneas / {aceptados} aceptados; {distintos} distintos / {esperados_distintos}",
        )

        # Cadencia: ficheros escritos durante la ejecución, uno cada ~30 s
        fechas = sorted(o["LastModified"] for o in objetos if inicio <= o["LastModified"] <= fin + timedelta(minutes=2))
        huecos = [(b - a).total_seconds() for a, b in zip(fechas, fechas[1:])]
        if huecos:
            mediana = statistics.median(huecos)
            detalle = f"mediana {mediana:.0f} s entre {len(fechas)} ficheros"
            criterio(20 <= mediana <= 45, "Un fichero nuevo cada ~30 s", detalle)
        else:
            criterio(None, "Un fichero nuevo cada ~30 s", "hacen falta al menos 2 ficheros de la ejecución")

        if resumen["invalidos_enviados"]:
            criterio(
                resumen["invalidos_rechazados"] == resumen["invalidos_enviados"],
                "Eventos inválidos rechazados con 422",
                f"{resumen['invalidos_rechazados']} de {resumen['invalidos_enviados']}",
            )

    # --- Errores de entrega -------------------------------------------------------
    errores = listar(s3, bucket, "errors/ventas/")
    print(f"\nerrors/ventas/: {len(errores)} ficheros")
    for o in errores[-10:]:
        print(f"  {o['LastModified']:%Y-%m-%d %H:%M:%S}  {o['Key']}")
    criterio(not errores, "Nada en errors/ (salvo pruebas provocadas)", f"{len(errores)} ficheros")

    # --- DataFreshness --------------------------------------------------------------
    cw = sesion.client("cloudwatch")
    ahora = datetime.now(UTC)
    datos = cw.get_metric_statistics(
        Namespace="AWS/Firehose",
        MetricName="DeliveryToS3.DataFreshness",
        Dimensions=[{"Name": "DeliveryStreamName", "Value": stream}],
        StartTime=ahora - timedelta(hours=3),
        EndTime=ahora,
        Period=60,
        Statistics=["Maximum"],
    )["Datapoints"]
    if datos:
        ultimo_dato = max(datos, key=lambda d: d["Timestamp"])
        maximo = max(d["Maximum"] for d in datos)
        hora = ultimo_dato["Timestamp"].astimezone(UTC)  # CloudWatch la devuelve en hora local
        print(
            f"\nDataFreshness: último {ultimo_dato['Maximum']:.0f} s ({hora:%H:%M} UTC), "
            f"máximo en 3 h {maximo:.0f} s"
        )
        criterio(maximo < 120, "DataFreshness por debajo de 2 minutos", f"máximo {maximo:.0f} s")
    else:
        criterio(None, "DataFreshness por debajo de 2 minutos", "sin datos en las últimas 3 h (¿generador parado?)")

    # --- Resultado ------------------------------------------------------------------------
    print("\nCriterios de aceptación")
    for estado, nombre, detalle in resultados:
        print(f"  [{estado}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    print("  [--] El evento inválido devuelve 422: python demo1-ingesta/scripts/evento_invalido.py")
    sys.exit(1 if any(r[0] == "KO" for r in resultados) else 0)


if __name__ == "__main__":
    main()
