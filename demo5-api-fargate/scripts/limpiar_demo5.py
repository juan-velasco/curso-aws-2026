"""Cierra la demo 5. Por defecto deja el service a 0 tareas, sin borrar nada.

Con --todo borra el service y el cluster, da de baja las revisiones de la task definition
y borra el repositorio de ECR, previo aviso: su imagen la usa el ejercicio G.

Uso:
    python demo5-api-fargate/scripts/limpiar_demo5.py [--perfil curso]
    python demo5-api-fargate/scripts/limpiar_demo5.py --todo [--si]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun.terraform import outputs  # noqa: E402

CLUSTER = "hp-retail"
SERVICIO = "api-ventas"
FAMILIA = "api-ventas"
REPOSITORIO = "api-ventas"


def servicio_activo(ecs) -> dict | None:
    try:
        servicios = ecs.describe_services(cluster=CLUSTER, services=[SERVICIO])["services"]
    except ecs.exceptions.ClusterNotFoundException:
        return None
    return next((s for s in servicios if s["status"] == "ACTIVE"), None)


def esperar_sin_tareas(ecs, limite_s: int = 180) -> None:
    fin = time.monotonic() + limite_s
    while time.monotonic() < fin:
        tareas = ecs.list_tasks(cluster=CLUSTER, serviceName=SERVICIO)["taskArns"]
        if not tareas:
            print("Ninguna tarea en marcha.")
            return
        print(f"  quedan {len(tareas)} tareas...")
        time.sleep(10)
    sys.exit("Sigue habiendo tareas: revísalo en la consola, porque tienen coste.")


def borrar_todo(ecs, ecr, confirmado: bool) -> None:
    if servicio_activo(ecs):
        ecs.delete_service(cluster=CLUSTER, service=SERVICIO, force=True)
        print(f"Service {SERVICIO} borrado.")
    try:
        ecs.delete_cluster(cluster=CLUSTER)
        print(f"Cluster {CLUSTER} borrado.")
    except ecs.exceptions.ClusterNotFoundException:
        pass

    revisiones = [
        arn
        for pagina in ecs.get_paginator("list_task_definitions").paginate(familyPrefix=FAMILIA, status="ACTIVE")
        for arn in pagina["taskDefinitionArns"]
    ]
    for arn in revisiones:
        ecs.deregister_task_definition(taskDefinition=arn)
    print(f"Revisiones dadas de baja: {len(revisiones)}.")

    print(f"Aviso: el ejercicio G compara con la imagen de {REPOSITORIO}. Si lo vas a hacer, conserva el repositorio.")
    if confirmado or input(f"¿Borrar el repositorio {REPOSITORIO} de ECR? [s/N] ").strip().lower() == "s":
        try:
            ecr.delete_repository(repositoryName=REPOSITORIO, force=True)
            print(f"Repositorio {REPOSITORIO} borrado.")
        except ecr.exceptions.RepositoryNotFoundException:
            pass
    else:
        print(f"Repositorio {REPOSITORIO} conservado.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    p.add_argument("--todo", action="store_true", help="Borra también service, cluster, revisiones y repositorio")
    p.add_argument("--si", action="store_true", help="No pregunta antes de borrar el repositorio")
    args = p.parse_args()

    sesion = boto3.Session(profile_name=args.perfil, region_name=outputs("demo5-api-fargate/infra")["region"])
    ecs = sesion.client("ecs")

    if servicio_activo(ecs):
        ecs.update_service(cluster=CLUSTER, service=SERVICIO, desiredCount=0)
        print(f"Service {SERVICIO} a 0 tareas.")
        esperar_sin_tareas(ecs)
    else:
        print("No hay service activo.")

    if args.todo:
        borrar_todo(ecs, sesion.client("ecr"), args.si)


if __name__ == "__main__":
    main()
