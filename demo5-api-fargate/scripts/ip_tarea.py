"""Muestra la IP pública de la tarea de la API: lista la tarea, lee su ENI y consulta la IP.

Uso:
    python demo5-api-fargate/scripts/ip_tarea.py [--perfil curso]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun.terraform import outputs  # noqa: E402

CLUSTER = "hp-retail"
SERVICIO = "api-ventas"


def eni_de_tarea(tarea: dict) -> str | None:
    for adjunto in tarea.get("attachments", []):
        if adjunto["type"] == "ElasticNetworkInterface":
            for detalle in adjunto["details"]:
                if detalle["name"] == "networkInterfaceId":
                    return detalle["value"]
    return None


def tarea_en_marcha(ecs) -> dict | None:
    """Tarea RUNNING del service, o None si no hay ninguna."""
    arns = ecs.list_tasks(cluster=CLUSTER, serviceName=SERVICIO, desiredStatus="RUNNING")["taskArns"]
    if not arns:
        return None
    tareas = ecs.describe_tasks(cluster=CLUSTER, tasks=arns)["tasks"]
    return next((t for t in tareas if t["lastStatus"] == "RUNNING"), None)


def ip_publica(ec2, tarea: dict) -> str | None:
    eni = eni_de_tarea(tarea)
    if eni is None:
        return None
    interfaz = ec2.describe_network_interfaces(NetworkInterfaceIds=[eni])["NetworkInterfaces"][0]
    return interfaz.get("Association", {}).get("PublicIp")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    sesion = boto3.Session(profile_name=args.perfil, region_name=outputs("demo5-api-fargate/infra")["region"])
    tarea = tarea_en_marcha(sesion.client("ecs"))
    if tarea is None:
        sys.exit("No hay ninguna tarea en RUNNING. Si acabas de crear el service, espera un minuto.")
    ip = ip_publica(sesion.client("ec2"), tarea)
    if ip is None:
        sys.exit("La tarea no tiene IP pública: revisa assignPublicIp=ENABLED en el service.")
    print(ip)


if __name__ == "__main__":
    main()
