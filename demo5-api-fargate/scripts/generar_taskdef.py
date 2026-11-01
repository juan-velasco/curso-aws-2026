"""Escribe demo5-api-fargate/taskdef.json con los ARN reales de los outputs de Terraform.

El fichero lleva el ID de cuenta y no se sube a git.

Uso:
    python demo5-api-fargate/scripts/generar_taskdef.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from comun.athena import sustituir  # noqa: E402
from comun.terraform import outputs  # noqa: E402

PLANTILLA = RAIZ / "demo5-api-fargate" / "taskdef.json.tpl"
SALIDA = RAIZ / "demo5-api-fargate" / "taskdef.json"
CLAVES_PROHIBIDAS = {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"}


def claves_aws(taskdef: dict) -> set[str]:
    """Variables de credenciales definidas en los contenedores. Debe salir vacío: las da el task role."""
    return {
        variable["name"]
        for contenedor in taskdef["containerDefinitions"]
        for variable in contenedor.get("environment", []) + contenedor.get("secrets", [])
        if variable["name"] in CLAVES_PROHIBIDAS
    }


def generar(plantilla: str, valores: dict[str, str]) -> dict:
    return json.loads(sustituir(plantilla, valores))


def main() -> None:
    tf = outputs("demo5-api-fargate/infra")
    valores = {
        clave: tf[clave]
        for clave in ("execution_role_arn", "task_role_arn", "account_id", "region", "stream_name", "log_group")
    }
    taskdef = generar(PLANTILLA.read_text(encoding="utf-8"), valores)
    SALIDA.write_text(json.dumps(taskdef, indent=2) + "\n", encoding="utf-8")
    print(f"Escrito {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
