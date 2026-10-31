"""Tests de la región de las tiendas, los tipos de cambio y el calendario."""

from datetime import date, timedelta
from decimal import Decimal

from comun import maestros, referencia


def test_region_de_las_tiendas():
    regiones = {t.tienda_id: t.region for t in maestros.tiendas()}
    assert regiones["ES-VLC-001"] == regiones["FR-PAR-001"] == regiones["ONL-ES"] == "Europa"
    assert regiones["US-NYC-001"] == regiones["ONL-US"] == "América"
    assert regiones["JP-TYO-001"] == regiones["CN-SHA-001"] == regiones["ONL-CN"] == "Asia"


def test_tipos_de_cambio():
    tipos = {t["moneda"]: t["eur_por_unidad"] for t in referencia.tipos_cambio()}
    assert tipos == {
        "EUR": Decimal("1.00000000"),
        "USD": Decimal("0.92592593"),
        "JPY": Decimal("0.00625000"),
        "CNY": Decimal("0.12820513"),
    }
    # El caso de las diapositivas: 6.392 JPY son 39,95 EUR
    assert round(6392 * tipos["JPY"], 2) == Decimal("39.95")


def test_calendario_cubre_todos_los_dias():
    dias = referencia.calendario()
    assert (dias[0].fecha, dias[-1].fecha) == (date(2024, 1, 1), date(2027, 12, 31))
    assert len(dias) == 1461  # 2024 es bisiesto
    assert all(b.fecha - a.fecha == timedelta(days=1) for a, b in zip(dias, dias[1:]))


def test_calendario_campos():
    dias = {d.fecha: d for d in referencia.calendario()}
    d = dias[date(2026, 10, 24)]
    assert (d.fecha_sk, d.anio, d.mes, d.nombre_mes) == (20261024, 2026, 10, "octubre")
    assert (d.semana_iso, d.dia_semana, d.nombre_dia, d.es_fin_de_semana) == (43, 6, "sábado", True)
    assert (d.temporada, d.es_rebajas, d.es_festivo) == ("OI", False, False)
    assert dias[date(2026, 10, 26)].es_fin_de_semana is False
    # Semana ISO en el cambio de año: 2027-01-01 cae en la semana 53 de 2026
    assert dias[date(2027, 1, 1)].semana_iso == 53


def test_temporada_rebajas_y_festivos():
    temporadas = {m: referencia.temporada(date(2026, m, 15)) for m in range(1, 13)}
    assert [m for m, t in temporadas.items() if t == "PV"] == [3, 4, 5, 6, 7, 8]
    for fecha, esperado in [
        (date(2026, 1, 6), False),
        (date(2026, 1, 7), True),
        (date(2026, 2, 28), True),
        (date(2026, 3, 1), False),
        (date(2026, 6, 30), False),
        (date(2026, 7, 1), True),
        (date(2026, 8, 31), True),
        (date(2026, 9, 1), False),
    ]:
        assert referencia.es_rebajas(fecha) is esperado, fecha
    festivos = [d.fecha for d in referencia.calendario() if d.es_festivo and d.anio == 2026]
    assert festivos == [date(2026, 1, 1), date(2026, 5, 1), date(2026, 12, 25)]
