"""Muestra el estado de GuardDuty e Inspector en la región. Solo lee. Lánzalo ANTES de crear nada.

Con --guardar escribe el estado en un fichero; con --comparar, tras destroy, comprueba que coincide.

Uso:
    python ejercicio-g-guardduty-inspector/scripts/estado_servicios.py [--perfil curso]
    python ejercicio-g-guardduty-inspector/scripts/estado_servicios.py --guardar
    python ejercicio-g-guardduty-inspector/scripts/estado_servicios.py --comparar
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

RAIZ = Path(__file__).resolve().parents[2]
FICHERO = RAIZ / "ejercicio-g-guardduty-inspector" / "salida" / "estado_inicial.json"
REGION = "eu-west-1"


def estado_guardduty(gd) -> dict:
    detectores = gd.list_detectors()["DetectorIds"]
    estado = {"detector": bool(detectores), "activo": False, "administrador": None}
    if detectores:
        estado["activo"] = gd.get_detector(DetectorId=detectores[0])["Status"] == "ENABLED"
        try:
            administrador = gd.get_administrator_account(DetectorId=detectores[0]).get("Administrator")
        except ClientError:
            administrador = None
        estado["administrador"] = administrador["AccountId"] if administrador else None
    return estado


def estado_inspector(inspector) -> dict:
    cuentas = inspector.batch_get_account_status()["accounts"]
    recursos = cuentas[0]["resourceState"] if cuentas else {}
    estado = {tipo: valor["status"] for tipo, valor in sorted(recursos.items())}
    try:
        administrador = inspector.get_delegated_admin_account().get("delegatedAdmin")
    except ClientError:  # sin permisos de organización, o la cuenta no pertenece a una
        administrador = None
    return {"recursos": estado, "administrador": administrador["accountId"] if administrador else None}


def recomendacion(gd: dict, inspector: dict) -> dict[str, bool]:
    """Qué puede activar Terraform: solo lo que no esté activo ni lo gestione la organización."""
    return {
        "crear_detector_guardduty": not gd["detector"],
        "activar_inspector_ecr": inspector["recursos"].get("ecr") == "DISABLED" and not inspector["administrador"],
    }


def comparable(estado: dict) -> dict:
    """Los tipos de recurso que no están desactivados: la API añade tipos nuevos según el servicio se activa."""
    inspector = estado["inspector"]
    activos = {tipo: valor for tipo, valor in inspector["recursos"].items() if valor != "DISABLED"}
    return {"guardduty": estado["guardduty"], "inspector": {**inspector, "recursos": activos}}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    p.add_argument("--guardar", action="store_true", help=f"Guarda el estado en {FICHERO.relative_to(RAIZ)}")
    p.add_argument("--comparar", action="store_true", help="Compara con el estado guardado")
    args = p.parse_args()

    sesion = boto3.Session(profile_name=args.perfil, region_name=REGION)
    gd = estado_guardduty(sesion.client("guardduty"))
    inspector = estado_inspector(sesion.client("inspector2"))
    estado = {"guardduty": gd, "inspector": inspector}

    detector = ("detector activo" if gd["activo"] else "detector suspendido") if gd["detector"] else "sin detector"
    print(f"GuardDuty ({REGION}): {detector}")
    print(f"  Administrador: {gd['administrador'] or 'ninguno (esta cuenta)'}")
    print(f"Inspector ({REGION}): {inspector['recursos']}")
    print(f"  Administrador delegado: {inspector['administrador'] or 'ninguno'}")
    print("Para terraform.tfvars:")
    for variable, valor in recomendacion(gd, inspector).items():
        print(f"  {variable} = {str(valor).lower()}")

    if args.guardar:
        FICHERO.parent.mkdir(exist_ok=True)
        FICHERO.write_text(json.dumps(estado, indent=2) + "\n", encoding="utf-8")
        print(f"Guardado en {FICHERO.relative_to(RAIZ)}")
    if args.comparar:
        inicial = json.loads(FICHERO.read_text(encoding="utf-8"))
        if comparable(estado) != comparable(inicial):
            sys.exit(f"El estado NO coincide con el inicial:\n{json.dumps(inicial, indent=2)}")
        print("El estado coincide con el inicial.")


if __name__ == "__main__":
    main()
