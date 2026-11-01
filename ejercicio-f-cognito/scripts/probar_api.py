"""Prueba la API: 401 sin token, 200 con el ID token, y muestra el contenido del token.

La contraseña se lee de la variable de entorno PASSWORD_TIENDA o se pide por teclado.

Uso:
    python ejercicio-f-cognito/scripts/probar_api.py [--perfil curso]
"""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun.terraform import outputs  # noqa: E402

USUARIO = "tienda-vlc-003"
CAMPOS = ("sub", "cognito:groups", "token_use", "iss", "exp")


def decodificar_jwt(token: str) -> dict:
    """Devuelve el payload SIN verificar la firma: sirve para mirarlo, no para confiar en él."""
    payload = token.split(".")[1]
    relleno = "=" * (-len(payload) % 4)  # base64url va sin relleno
    return json.loads(base64.urlsafe_b64decode(payload + relleno))


def llamar(url: str, token: str | None = None) -> tuple[int, str]:
    peticion = urllib.request.Request(url, headers={"Authorization": token} if token else {})
    try:
        with urllib.request.urlopen(peticion, timeout=15) as respuesta:
            return respuesta.status, respuesta.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    tf = outputs("ejercicio-f-cognito/infra")
    cognito = boto3.Session(profile_name=args.perfil, region_name=tf["region"]).client("cognito-idp")
    password = os.environ.get("PASSWORD_TIENDA") or getpass.getpass(f"Contraseña de {USUARIO}: ")

    estado, cuerpo = llamar(tf["url_api"])
    print(f"Sin token: HTTP {estado} {cuerpo.strip()}")
    sin_token_ok = estado == 401

    tokens = cognito.initiate_auth(
        ClientId=tf["client_id"],
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": USUARIO, "PASSWORD": password},
    )["AuthenticationResult"]
    id_token = tokens["IdToken"]

    estado, cuerpo = llamar(tf["url_api"], id_token)
    print(f"Con token: HTTP {estado} {cuerpo.strip()}")
    con_token_ok = estado == 200

    contenido = decodificar_jwt(id_token)
    print("Payload del ID token (sin verificar la firma):")
    print(json.dumps({campo: contenido.get(campo) for campo in CAMPOS}, indent=2, ensure_ascii=False))
    grupo_ok = "tiendas" in contenido.get("cognito:groups", [])

    print("Criterios de aceptación")
    for ok, nombre in (
        (sin_token_ok, "401 sin token"),
        (con_token_ok, "200 con token"),
        (grupo_ok, "Grupo tiendas en el token"),
    ):
        print(f"  [{'OK' if ok else 'FALLO'}] {nombre}")
    if not (sin_token_ok and con_token_ok and grupo_ok):
        sys.exit(1)


if __name__ == "__main__":
    main()
