import importlib.util
from datetime import datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "comprobar_bronze.py"
spec = importlib.util.spec_from_file_location("comprobar_bronze", SCRIPT)
comprobar_bronze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comprobar_bronze)

RESUMEN = {"inicio": "2026-11-01T23:50:00Z", "fin": "2026-11-02T00:05:00Z"}


def test_resumen_del_dia_de_la_ejecucion():
    assert comprobar_bronze.resumen_de_la_fecha(RESUMEN, datetime(2026, 11, 1))
    assert comprobar_bronze.resumen_de_la_fecha(RESUMEN, datetime(2026, 11, 2))


def test_resumen_de_otro_dia_no_se_compara():
    assert not comprobar_bronze.resumen_de_la_fecha(RESUMEN, datetime(2026, 10, 28))
