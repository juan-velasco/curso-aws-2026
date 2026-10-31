"""Comprueba la definición de la máquina de estados, tal como la renderiza Terraform."""

import json
import re
from pathlib import Path

import pytest

PLANTILLA = Path(__file__).resolve().parents[1] / "pipeline.asl.json"
PASS_SPICE = {"Type": "Pass", "Next": "NotificarOK"}
TASK_SPICE = {
    "Type": "Task",
    "Resource": "arn:aws:states:::aws-sdk:quicksight:createIngestion",
    "Parameters": {"AwsAccountId": "1", "DataSetId": "d", "IngestionId.$": "States.UUID()"},
    "Next": "NotificarOK",
}


def renderizar(refrescar):
    valores = {
        "refrescar_spice": json.dumps(refrescar), "job_ventas": "ventas", "job_maestros": "maestros",
        "bucket": "lago", "clave_control": "control/x.json", "workgroup": "hp-retail", "tema_sns": "arn:sns",
    }  # fmt: skip
    return json.loads(re.sub(r"\$\{(\w+)\}", lambda m: valores[m.group(1)], PLANTILLA.read_text(encoding="utf-8")))


@pytest.fixture(params=[PASS_SPICE, TASK_SPICE], ids=["sin_quicksight", "con_quicksight"])
def maquina(request):
    return renderizar(request.param)


def destinos(estado):
    if "Next" in estado:
        yield estado["Next"]
    if "Default" in estado:
        yield estado["Default"]
    for choice in estado.get("Choices", []):
        yield choice["Next"]
    for catch in estado.get("Catch", []):
        yield catch["Next"]


def test_todos_los_estados_son_alcanzables_y_existen(maquina):
    estados = maquina["States"]
    vistos, pendientes = set(), [maquina["StartAt"]]
    while pendientes:
        nombre = pendientes.pop()
        if nombre not in vistos:
            vistos.add(nombre)
            pendientes += destinos(estados[nombre])
    assert vistos == set(estados)


def test_el_camino_de_la_diapositiva(maquina):
    e = maquina["States"]
    assert e["SilverEnParalelo"]["Next"] == "LeerCalidad"
    assert e["LeerCalidad"]["ResultSelector"] == {"control.$": "States.StringToJson($.Body)"}
    assert e["CalidadOK"]["Default"] == "CargarGold"
    sin_datos, calidad = e["CalidadOK"]["Choices"]
    assert (sin_datos["NumericEquals"], sin_datos["Next"]) == (0, "SinDatos")
    assert (calidad["NumericGreaterThan"], calidad["Next"]) == (5, "NotificarFallo")
    assert e["GoldTerminado"]["Choices"][0]["Next"] == "RefrescarSPICE"
    assert e["RefrescarSPICE"]["Next"] == "NotificarOK"
    assert e["NotificarFallo"]["Next"] == "Fallido"


def test_los_jobs_reciben_forzar_fallo(maquina):
    for rama in maquina["States"]["SilverEnParalelo"]["Branches"]:
        job = next(iter(rama["States"].values()))
        assert job["Parameters"]["Arguments"] == {"--FORZAR_FALLO.$": "$.opciones.forzar_fallo"}
