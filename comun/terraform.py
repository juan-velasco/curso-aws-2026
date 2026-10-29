"""Lectura de los outputs de Terraform desde los scripts de apoyo."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def outputs(modulo: str) -> dict:
    """Devuelve los outputs de un módulo (ruta relativa a la raíz del repositorio).

    Ejemplo: outputs("demo1-ingesta/infra")["stream_name"]
    """
    directorio = RAIZ / modulo
    if shutil.which("terraform") is None:
        sys.exit("No se encuentra 'terraform' en el PATH.")
    proceso = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=directorio,
        capture_output=True,
        text=True,
    )
    if proceso.returncode != 0:
        sys.exit(f"Error leyendo los outputs de {modulo}:\n{proceso.stderr}")
    datos = {nombre: valor["value"] for nombre, valor in json.loads(proceso.stdout or "{}").items()}
    if not datos:
        sys.exit(f"El módulo {modulo} no tiene outputs. ¿Has ejecutado 'terraform apply' en él?")
    return datos
