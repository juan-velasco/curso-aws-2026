"""Utilidades comunes de los scripts de la demo 2: outputs de Terraform, AWS y PostgreSQL."""

from __future__ import annotations

import os
import sys
from functools import cache
from pathlib import Path

import boto3
import psycopg

RAIZ = Path(__file__).resolve().parents[2]
SQL = RAIZ / "demo2-cdc-dms" / "sql"
sys.path.insert(0, str(RAIZ))

from comun.terraform import outputs  # noqa: E402


@cache
def tf() -> dict:
    return outputs("demo2-cdc-dms/infra")


def sesion_aws(perfil: str | None = None) -> boto3.Session:
    return boto3.Session(profile_name=perfil or os.environ.get("AWS_PROFILE", "curso"), region_name=tf()["region"])


def conectar_maestro() -> psycopg.Connection:
    """Conexión a RDS con el usuario maestro (contraseña del estado de Terraform)."""
    o = tf()
    return psycopg.connect(
        host=o["rds_endpoint"],
        port=o["rds_port"],
        dbname=o["db_name"],
        user=o["usuario_maestro"],
        password=o["password_maestra"],
        sslmode="require",
        connect_timeout=10,
    )
