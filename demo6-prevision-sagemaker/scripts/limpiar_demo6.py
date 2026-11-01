"""Para las apps de Studio y comprueba que no hay endpoints ni trabajos en curso.

Con --todo borra también los spaces (su volumen EBS tiene coste aunque estén parados) y los modelos
registrados en prevision-ventas: es el paso previo a terraform destroy.

Uso:
    python demo6-prevision-sagemaker/scripts/limpiar_demo6.py [--perfil curso]
    python demo6-prevision-sagemaker/scripts/limpiar_demo6.py --todo
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun.terraform import outputs  # noqa: E402

GRUPO_MODELOS = "prevision-ventas"
ESTADOS_EN_MARCHA = {"InService", "Pending", "Updating"}


def apps_en_marcha(sm, dominio: str) -> list[dict]:
    return [
        app
        for pagina in sm.get_paginator("list_apps").paginate(DomainIdEquals=dominio)
        for app in pagina["Apps"]
        if app["Status"] in ESTADOS_EN_MARCHA
    ]


def parar_apps(sm, dominio: str, limite_s: int = 600) -> None:
    apps = apps_en_marcha(sm, dominio)
    for app in apps:
        dueno = {"SpaceName": app["SpaceName"]} if app.get("SpaceName") else {"UserProfileName": app["UserProfileName"]}
        sm.delete_app(DomainId=dominio, AppType=app["AppType"], AppName=app["AppName"], **dueno)
        print(f"Parando {app['AppType']} {app['AppName']}...")
    fin = time.monotonic() + limite_s
    while apps_en_marcha(sm, dominio) or apps_borrando(sm, dominio):
        if time.monotonic() > fin:
            sys.exit("Sigue habiendo apps en marcha: revísalo en la consola, porque tienen coste.")
        time.sleep(15)
    print("Ninguna app en marcha.")


def apps_borrando(sm, dominio: str) -> bool:
    return any(
        app["Status"] == "Deleting"
        for pagina in sm.get_paginator("list_apps").paginate(DomainIdEquals=dominio)
        for app in pagina["Apps"]
    )


def borrar_spaces(sm, dominio: str, limite_s: int = 300) -> None:
    spaces = sm.list_spaces(DomainIdEquals=dominio)["Spaces"]
    for space in spaces:
        if space["Status"] != "Deleting":
            sm.delete_space(DomainId=dominio, SpaceName=space["SpaceName"])
            print(f"Borrando el space {space['SpaceName']}...")
    fin = time.monotonic() + limite_s
    while sm.list_spaces(DomainIdEquals=dominio)["Spaces"]:
        if time.monotonic() > fin:
            sys.exit("Sigue habiendo spaces: revísalo en la consola.")
        time.sleep(10)
    print("Ningún space.")


def borrar_modelos(sm) -> None:
    try:
        paquetes = sm.list_model_packages(ModelPackageGroupName=GRUPO_MODELOS)["ModelPackageSummaryList"]
        for paquete in paquetes:
            sm.delete_model_package(ModelPackageName=paquete["ModelPackageArn"])
        sm.delete_model_package_group(ModelPackageGroupName=GRUPO_MODELOS)
        print(f"Grupo {GRUPO_MODELOS} borrado, con {len(paquetes)} versiones.")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ValidationException":
            raise
        print(f"No hay grupo {GRUPO_MODELOS}.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    p.add_argument("--todo", action="store_true", help="Borra también los spaces y los modelos registrados")
    args = p.parse_args()

    tf = outputs("demo6-prevision-sagemaker/infra")
    sm = boto3.Session(profile_name=args.perfil, region_name=tf["region"]).client("sagemaker")

    parar_apps(sm, tf["dominio_id"])
    if args.todo:
        borrar_spaces(sm, tf["dominio_id"])
        borrar_modelos(sm)

    endpoints = [e["EndpointName"] for e in sm.list_endpoints()["Endpoints"]]
    entrenando = sm.list_training_jobs(StatusEquals="InProgress")["TrainingJobSummaries"]
    transformando = sm.list_transform_jobs(StatusEquals="InProgress")["TransformJobSummaries"]
    print(f"Endpoints: {len(endpoints)}. En curso: {len(entrenando)} training jobs, {len(transformando)} transform.")
    if endpoints or entrenando or transformando:
        sys.exit(f"Revísalo en la consola, porque tiene coste: {endpoints or ''}")


if __name__ == "__main__":
    main()
