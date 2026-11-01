"""Crea el usuario de prueba tienda-vlc-003, en estado CONFIRMED y dentro del grupo tiendas. Se puede repetir.

La contraseña se lee de la variable de entorno PASSWORD_TIENDA o se pide por teclado; nunca va en un fichero.
Política por defecto de Cognito: 8 caracteres, con mayúscula, minúscula, número y símbolo.

Uso:
    python ejercicio-f-cognito/scripts/crear_usuario.py [--perfil curso]
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun.terraform import outputs  # noqa: E402

USUARIO = "tienda-vlc-003"
GRUPO = "tiendas"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    tf = outputs("ejercicio-f-cognito/infra")
    cognito = boto3.Session(profile_name=args.perfil, region_name=tf["region"]).client("cognito-idp")
    password = os.environ.get("PASSWORD_TIENDA") or getpass.getpass(f"Contraseña para {USUARIO}: ")

    try:
        cognito.admin_create_user(UserPoolId=tf["user_pool_id"], Username=USUARIO, MessageAction="SUPPRESS")
        print(f"Usuario {USUARIO} creado.")
    except cognito.exceptions.UsernameExistsException:
        print(f"El usuario {USUARIO} ya existía.")
    cognito.admin_set_user_password(
        UserPoolId=tf["user_pool_id"], Username=USUARIO, Password=password, Permanent=True
    )
    cognito.admin_add_user_to_group(UserPoolId=tf["user_pool_id"], Username=USUARIO, GroupName=GRUPO)
    estado = cognito.admin_get_user(UserPoolId=tf["user_pool_id"], Username=USUARIO)["UserStatus"]
    print(f"Estado: {estado}. Grupo: {GRUPO}.")


if __name__ == "__main__":
    main()
