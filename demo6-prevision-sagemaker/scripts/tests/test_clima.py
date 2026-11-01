import io
from datetime import date

import pyarrow.parquet as pq

from generar_clima import PERFILES, a_parquet, generar

INICIO, FIN = date(2026, 7, 2), date(2026, 11, 28)


def test_una_fila_por_pais_y_dia():
    filas = generar(INICIO, FIN)
    dias = (FIN - INICIO).days + 1
    assert len(filas) == dias * 5
    assert len({(f["fecha_sk"], f["pais"]) for f in filas}) == len(filas)
    assert {f["pais"] for f in filas} == set(PERFILES) == {"ES", "FR", "US", "JP", "CN"}


def test_cubre_las_fechas_de_la_prevision():
    fechas = {f["fecha_sk"] for f in generar(INICIO, FIN)}
    assert min(fechas) == 20260702
    assert max(fechas) == 20261128


def test_es_determinista():
    assert generar(INICIO, FIN) == generar(INICIO, FIN)


def test_ampliar_el_rango_no_cambia_lo_generado():
    corto = {(f["fecha_sk"], f["pais"]): f for f in generar(INICIO, date(2026, 8, 1))}
    largo = {(f["fecha_sk"], f["pais"]): f for f in generar(INICIO, FIN)}
    assert all(largo[clave] == fila for clave, fila in corto.items())


def test_rangos_razonables():
    filas = generar(date(2026, 1, 1), date(2026, 12, 31))
    assert all(-15 <= f["temp_media"] <= 45 for f in filas)
    assert all(f["lluvia_mm"] >= 0 for f in filas)
    secos = sum(f["lluvia_mm"] == 0 for f in filas)
    assert 0.5 < secos / len(filas) < 0.9


def test_verano_mas_calido_que_invierno():
    filas = generar(date(2026, 1, 1), date(2026, 12, 31))
    media = lambda mes: _media([f["temp_media"] for f in filas if f["fecha_sk"] // 100 == 202600 + mes])  # noqa: E731
    assert media(7) > media(1) + 5


def _media(valores):
    return sum(valores) / len(valores)


def test_parquet_con_las_columnas_del_notebook():
    tabla = pq.read_table(io.BytesIO(a_parquet(generar(INICIO, INICIO))))
    assert tabla.column_names == ["fecha_sk", "pais", "temp_media", "lluvia_mm"]
    assert tabla.num_rows == 5
