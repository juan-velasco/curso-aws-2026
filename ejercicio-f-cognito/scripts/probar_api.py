"""Prueba la API: 401 sin token, 200 con el ID token, y muestra el contenido del token.

Por defecto lee los outputs de Terraform. Si la montaste en la consola, indica --url y --client-id.
La contraseña se lee de la variable de entorno PASSWORD_TIENDA o se pide por teclado.
Con --decodificar solo muestra el contenido de un token: en local, sin pegarlo en una web de terceros.

Uso:
    python ejercicio-f-cognito/scripts/probar_api.py [--perfil curso]
    python ejercicio-f-cognito/scripts/probar_api.py --url <url>/prod/hola --client-id <id> [--usuario <usuario>]
    python ejercicio-f-cognito/scripts/probar_api.py --decodificar <token>
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
REGION = "eu-west-1"


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


def crear_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    p.add_argument("--url", help="URL de GET /hola. Con --client-id, no se usa Terraform")
    p.add_argument("--client-id", help="ID del app client. Con --url, no se usa Terraform")
    p.add_argument("--usuario", default=USUARIO, help=f"Por defecto, {USUARIO}")
    p.add_argument("--region", default=REGION, help=f"Región del user pool con --url. Por defecto, {REGION}")
    p.add_argument("--decodificar", metavar="TOKEN", help="Muestra el contenido del token y termina")
    return p


def destino(args: argparse.Namespace, p: argparse.ArgumentParser) -> tuple[str, str, str]:
    """URL, app client y región: de los argumentos o, sin ellos, de Terraform."""
    if bool(args.url) != bool(args.client_id):
        p.error("--url y --client-id van juntos")
    if args.url:
        return args.url, args.client_id, args.region
    tf = outputs("ejercicio-f-cognito/infra")
    return tf["url_api"], tf["client_id"], tf["region"]


def pedir_id_token(cognito, client_id: str, usuario: str, password: str) -> str:
    respuesta = cognito.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": usuario, "PASSWORD": password},
    )
    if "AuthenticationResult" not in respuesta:
        sys.exit(
            f"Cognito no da tokens: pide el reto {respuesta.get('ChallengeName')}. "
            "Si es NEW_PASSWORD_REQUIRED, el usuario está en FORCE_CHANGE_PASSWORD: "
            "falta admin-set-user-password --permanent."
        )
    return respuesta["AuthenticationResult"]["IdToken"]


def main() -> None:
    p = crear_parser()
    args = p.parse_args()

    if args.decodificar:
        print(json.dumps(decodificar_jwt(args.decodificar), indent=2, ensure_ascii=False))
        return

    url, client_id, region = destino(args, p)
    cognito = boto3.Session(profile_name=args.perfil, region_name=region).client("cognito-idp")
    password = os.environ.get("PASSWORD_TIENDA") or getpass.getpass(f"Contraseña de {args.usuario}: ")

    estado, cuerpo = llamar(url)
    print(f"Sin token: HTTP {estado} {cuerpo.strip()}")
    sin_token_ok = estado == 401

    id_token = pedir_id_token(cognito, client_id, args.usuario, password)

    estado, cuerpo = llamar(url, id_token)
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
    terminado = sin_token_ok and con_token_ok
    print(f"Terminado (401 sin token y 200 con token): {'SÍ' if terminado else 'NO'}")
    if not (terminado and grupo_ok):
        sys.exit(1)


if __name__ == "__main__":
    main()
