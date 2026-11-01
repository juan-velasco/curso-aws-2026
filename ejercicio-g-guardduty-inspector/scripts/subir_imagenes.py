"""Descarga python:3.8, la etiqueta y la sube a curso-imagen-antigua.

La imagen slim de la API ya está en api-ventas desde la demo 5.

Uso:
    python ejercicio-g-guardduty-inspector/scripts/subir_imagenes.py [--perfil curso]
"""

from __future__ import annotations

import argparse
import base64
import os
import subprocess
import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun.terraform import outputs  # noqa: E402

IMAGEN = "python:3.8"
ETIQUETA = "3.8"


def docker(*argumentos: str, entrada: str | None = None) -> None:
    subprocess.run(["docker", *argumentos], input=entrada, text=True, check=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    tf = outputs("ejercicio-g-guardduty-inspector/infra")
    ecr = boto3.Session(profile_name=args.perfil, region_name=tf["region"]).client("ecr")
    autorizacion = ecr.get_authorization_token()["authorizationData"][0]
    usuario, password = base64.b64decode(autorizacion["authorizationToken"]).decode().split(":", 1)

    destino = f"{tf['repositorio_antigua']}:{ETIQUETA}"
    docker("login", "--username", usuario, "--password-stdin", autorizacion["proxyEndpoint"], entrada=password)
    docker("pull", IMAGEN)
    docker("tag", IMAGEN, destino)
    docker("push", destino)
    print(f"Subida la imagen curso-imagen-antigua:{ETIQUETA}. Inspector la escanea en unos minutos.")


if __name__ == "__main__":
    main()
