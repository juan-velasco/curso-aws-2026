"""Tests de los literales y lotes de la carga de referencia."""

from datetime import date
from decimal import Decimal

from cargar_referencia import filas_calendario, filas_tiendas, filas_tipos_cambio, inserts, literal


def test_literales():
    assert literal(None) == "NULL"
    assert literal(True) == "true"
    assert literal(850) == "850"
    assert literal(date(2026, 10, 24)) == "DATE '2026-10-24'"
    assert literal(Decimal("0.00625000")) == "DECIMAL '0.00625000'"
    assert literal("L'Oréal") == "'L''Oréal'"


def test_lotes():
    filas = [(n, "x") for n in range(1200)]
    sentencias = list(inserts("calendario", filas))
    assert len(sentencias) == 3
    assert sentencias[0].startswith("INSERT INTO silver.calendario VALUES\n(0, 'x'),")


def test_filas_en_el_orden_de_las_tablas():
    assert len(filas_tiendas()) == 26
    online = next(f for f in filas_tiendas() if f[0] == "ONL-JP")
    assert online == ("ONL-JP", "Online Japón", "JP", "Asia", "online", "online", None, True, "JPY")
    assert ("JPY", Decimal("0.00625000")) in filas_tipos_cambio()
    primera = filas_calendario()[0]
    assert primera[:4] == (20240101, date(2024, 1, 1), 2024, 1)
    assert primera[-3:] == ("OI", False, True)
