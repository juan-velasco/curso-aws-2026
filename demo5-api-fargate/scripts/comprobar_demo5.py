"""Revisa los criterios de aceptación de la demo 5.

Con --parado comprueba el cierre: service a 0 y ninguna tarea en marcha.

Uso:
    python demo5-api-fargate/scripts/comprobar_demo5.py [--desde 2026-11-01T10:00:00Z] [--perfil curso]
    python demo5-api-fargate/scripts/comprobar_demo5.py --parado
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

import boto3

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun.terraform import outputs  # noqa: E402
from generar_taskdef import claves_aws  # noqa: E402
from ip_tarea import CLUSTER, SERVICIO, ip_publica, tarea_en_marcha  # noqa: E402

resultados: list[tuple[bool, str, str]] = []


def criterio(estado: bool, nombre: str, detalle: str = "") -> None:
    resultados.append((estado, nombre, detalle))


def informe() -> None:
    print("Criterios de aceptación")
    for estado, nombre, detalle in resultados:
        print(f"  [{'OK' if estado else 'FALLO'}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    if not all(estado for estado, _, _ in resultados):
        sys.exit(1)


def comprobar_parado(ecs) -> None:
    servicios = ecs.describe_services(cluster=CLUSTER, services=[SERVICIO])["services"]
    deseadas = servicios[0]["desiredCount"] if servicios else 0
    tareas = ecs.list_tasks(cluster=CLUSTER, serviceName=SERVICIO)["taskArns"] if servicios else []
    criterio(deseadas == 0, "Service con desired-count 0", f"desired-count = {deseadas}")
    criterio(not tareas, "Ninguna tarea en marcha", f"{len(tareas)} tareas")


def health(ip: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(f"http://{ip}:8000/health", timeout=10) as respuesta:
            return respuesta.status == 200, f"HTTP {respuesta.status}"
    except (urllib.error.URLError, TimeoutError) as e:
        return False, str(e)


def ficheros_desde(s3, bucket: str, desde: datetime) -> int:
    """Ficheros de Firehose (no los del backfill) escritos en bronze desde esa hora, día a día en UTC."""
    total, dia, hoy = 0, desde.date(), datetime.now(UTC).date()
    while dia <= hoy:
        prefijo = f"bronze/ventas/anio={dia:%Y}/mes={dia:%m}/dia={dia:%d}/"
        for pagina in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefijo):
            total += sum(
                1
                for o in pagina.get("Contents", [])
                if o["LastModified"] >= desde and "backfill-" not in o["Key"]
            )
        dia += timedelta(days=1)
    return total


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    p.add_argument("--desde", help="Hora de inicio en UTC, ISO 8601. Por defecto, cuando arrancó la tarea")
    p.add_argument("--parado", action="store_true", help="Comprueba el cierre de la demo")
    args = p.parse_args()

    tf = outputs("demo5-api-fargate/infra")
    sesion = boto3.Session(profile_name=args.perfil, region_name=tf["region"])
    ecs = sesion.client("ecs")

    if args.parado:
        comprobar_parado(ecs)
        informe()
        return

    tarea = tarea_en_marcha(ecs)
    criterio(tarea is not None, "Tarea en estado RUNNING")
    if tarea is None:
        informe()
        return

    ip = ip_publica(sesion.client("ec2"), tarea)
    ok, detalle = health(ip) if ip else (False, "sin IP pública")
    criterio(ok, "/health responde desde este equipo", detalle)

    desde = datetime.fromisoformat(args.desde) if args.desde else tarea["startedAt"]
    desde = desde.replace(tzinfo=desde.tzinfo or UTC).astimezone(UTC)  # boto3 devuelve hora local

    streams = sesion.client("logs").describe_log_streams(
        logGroupName=tf["log_group"], orderBy="LastEventTime", descending=True, limit=1
    )["logStreams"]
    reciente = bool(streams) and streams[0].get("lastEventTimestamp", 0) >= desde.timestamp() * 1000
    stream = streams[0]["logStreamName"] if streams else "sin streams"
    criterio(reciente, f"Logs recientes en {tf['log_group']}", stream)

    nuevos = ficheros_desde(sesion.client("s3"), tf["bucket_name"], desde)
    criterio(nuevos > 0, "Ficheros nuevos en bronze/ventas", f"{nuevos} desde {desde:%H:%M:%S} UTC")

    taskdef = ecs.describe_task_definition(taskDefinition=tarea["taskDefinitionArn"])["taskDefinition"]
    claves = claves_aws(taskdef)
    criterio(not claves, "Sin claves AWS en la task definition", ", ".join(sorted(claves)))
    criterio(
        taskdef.get("taskRoleArn") == tf["task_role_arn"], "Las credenciales vienen del task role", "api-ventas-task"
    )
    informe()


if __name__ == "__main__":
    main()
