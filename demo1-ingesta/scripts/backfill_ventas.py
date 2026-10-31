"""Histórico de ventas directo a bronze, sin pasar por la API ni por Firehose.

Escribe en el mismo formato que Firehose (JSON Lines en gzip, un evento por línea):
    bronze/ventas/anio=AAAA/mes=MM/dia=DD/backfill-AAAA-MM-DD-NNN.json.gz

La fecha de la carpeta es la del evento: simula que llegó ese día. Es idempotente:
salta los días que ya tienen ficheros backfill- (salvo con --forzar, que los
sustituye) y nunca toca los ficheros de Firehose. Los datos de cada día son
deterministas, así que repetirlo genera exactamente lo mismo.

Uso:
    python demo1-ingesta/scripts/backfill_ventas.py [--dias 120] [--eventos-dia 1500]
        [--duplicados-pct 2] [--hasta AAAA-MM-DD] [--forzar] [--perfil curso]
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import random
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import eventos as ev  # noqa: E402
from comun.terraform import outputs  # noqa: E402

EVENTOS_POR_FICHERO = 2000
SEGUNDOS_DIA = 86400


def generar_dia(fecha: date, eventos_dia: int, duplicados_pct: float) -> list[dict]:
    """Eventos de un día en orden de event_ts, con los duplicados al final."""
    rng = random.Random(f"2026-backfill-{fecha}")
    fabrica = ev.FabricaVentas(
        rng, secuencia_inicial=0, nuevo_id=lambda: str(uuid.UUID(int=rng.getrandbits(128), version=4))
    )
    pesos = ev.pesos_productos(fecha)
    medianoche = datetime(fecha.year, fecha.month, fecha.day, tzinfo=UTC)

    num_tickets = max(1, round(ev.eventos_del_dia(fecha, eventos_dia) / ev.MEDIA_LINEAS))
    # Hora a hora el reparto es uniforme: las tiendas están en husos horarios de todo el mundo
    segundos = sorted(rng.uniform(0, SEGUNDOS_DIA - 0.001) for _ in range(num_tickets))
    lineas = [e for s in segundos for e in fabrica.ticket(medianoche + timedelta(seconds=s), pesos)]
    # Como en el generador, los duplicados llegan más tarde: el reintento de un TPV sin respuesta
    copias = [dict(e) for e in lineas if rng.random() * 100 < duplicados_pct]
    return lineas + copias


def prefijo_dia(fecha: date) -> str:
    return f"bronze/ventas/anio={fecha:%Y}/mes={fecha:%m}/dia={fecha:%d}/"


def claves_backfill(s3, bucket: str, fecha: date) -> list[str]:
    paginas = s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=f"{prefijo_dia(fecha)}backfill-")
    return [o["Key"] for pagina in paginas for o in pagina.get("Contents", [])]


def escribir_dia(s3, bucket: str, fecha: date, eventos: list[dict]) -> int:
    """Sube los eventos en ficheros gzip y devuelve cuántos ficheros ha escrito."""
    ficheros = 0
    for inicio in range(0, len(eventos), EVENTOS_POR_FICHERO):
        trozo = eventos[inicio : inicio + EVENTOS_POR_FICHERO]
        cuerpo = "".join(json.dumps(e) + "\n" for e in trozo).encode("utf-8")
        s3.put_object(
            Bucket=bucket,
            Key=f"{prefijo_dia(fecha)}backfill-{fecha}-{ficheros:03d}.json.gz",
            Body=gzip.compress(cuerpo, mtime=0),
            ContentType="application/octet-stream",
            ContentEncoding="gzip",  # los mismos metadatos que pone Firehose
        )
        ficheros += 1
    return ficheros


def rellenar(
    s3, bucket: str, hasta: date, dias: int, eventos_dia: int, duplicados_pct: float, forzar: bool = False
) -> dict:
    """Rellena `dias` días terminando en `hasta` y devuelve los totales."""
    totales = {"dias_escritos": 0, "dias_saltados": 0, "eventos": 0, "ficheros": 0}
    for n in range(dias - 1, -1, -1):
        fecha = hasta - timedelta(days=n)
        existentes = claves_backfill(s3, bucket, fecha)
        if existentes and not forzar:
            totales["dias_saltados"] += 1
            continue
        for clave in existentes:
            s3.delete_object(Bucket=bucket, Key=clave)
        eventos = generar_dia(fecha, eventos_dia, duplicados_pct)
        totales["ficheros"] += escribir_dia(s3, bucket, fecha, eventos)
        totales["eventos"] += len(eventos)
        totales["dias_escritos"] += 1
        print(f"  {fecha}: {len(eventos)} eventos")
    return totales


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dias", type=int, default=120, help="días de histórico (120 cubre las rebajas de verano)")
    p.add_argument("--eventos-dia", type=int, default=1500, help="eventos de un día laborable fuera de rebajas")
    p.add_argument("--duplicados-pct", type=float, default=2, help="porcentaje de eventos reenviados")
    p.add_argument("--hasta", type=date.fromisoformat, help="último día AAAA-MM-DD (por defecto, ayer en UTC)")
    p.add_argument("--forzar", action="store_true", help="sustituye los ficheros backfill- que ya existan")
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    tf = outputs("infra/base")
    hasta = args.hasta or datetime.now(UTC).date() - timedelta(days=1)
    s3 = boto3.Session(profile_name=args.perfil, region_name=tf["region"]).client("s3")
    print(f"Backfill en s3://{tf['bucket_name']}/bronze/ventas/: {args.dias} días hasta {hasta}")
    totales = rellenar(s3, tf["bucket_name"], hasta, args.dias, args.eventos_dia, args.duplicados_pct, args.forzar)
    print(
        f"\nDías escritos: {totales['dias_escritos']} ({totales['dias_saltados']} ya estaban). "
        f"Eventos: {totales['eventos']}. Ficheros: {totales['ficheros']}."
    )


if __name__ == "__main__":
    main()
