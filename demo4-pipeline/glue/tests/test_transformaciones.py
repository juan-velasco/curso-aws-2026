"""Tests de las transformaciones de bronze a silver con PySpark local."""

from datetime import date
from decimal import Decimal

import pytest

from transformaciones import (
    CLIENTES,
    PRODUCTOS,
    a_cuarentena,
    aplicar_scd2,
    control_calidad,
    fuente_rota,
    transformar_ventas,
)

FIN = date(9999, 12, 31)
INICIO = date(1900, 1, 1)
DIA = date(2026, 10, 28)
SIGUIENTE = date(2026, 10, 29)

CLIENTE_17 = {
    "cliente_id": "C-17", "nombre": "Lucía García", "email": "cliente17@ejemplo.com",
    "telefono": "+34 600 000 017", "segmento": "Standard", "provincia": "Valencia", "pais": "ES",
    "fecha_alta": date(2025, 1, 10),
}  # fmt: skip
CARGA = "2026-10-28 17:20:00.000000"
CAMBIO = "2026-10-28 17:23:34.470161"
OTRO_DIA = "2026-10-29 09:00:00.000000"


def fila(ts, op=None, base=CLIENTE_17, **cambios):
    return {"Op": op, "ts_commit": ts, **base, **cambios}


def lote(spark, filas):
    return spark.createDataFrame(filas, schema=_esquema_lote())


def _esquema_lote():
    return (
        "Op string, ts_commit string, cliente_id string, nombre string, email string, telefono string, "
        "segmento string, provincia string, pais string, fecha_alta date"
    )


def dim_vacia(spark, maestro=CLIENTES):
    return spark.createDataFrame([], maestro.esquema)


def versiones(spark, filas, dim=None):
    df = aplicar_scd2(spark, CLIENTES, dim if dim is not None else dim_vacia(spark), lote(spark, filas))
    return sorted((f.asDict() for f in df.collect()), key=lambda v: (v["cliente_id"], v["valid_from"]))


def resumen(v):
    return (v["segmento"], v["valid_from"], v["valid_to"], v["is_current"], v["es_baja"])


# --- 1. Arranque ----------------------------------------------------------------------


def test_arranque_solo_con_la_carga_completa(spark):
    v = versiones(spark, [fila(CARGA), fila(CARGA, cliente_id="C-2", segmento="Premium")])
    assert [resumen(x) for x in v] == [
        ("Standard", INICIO, FIN, True, False),
        ("Premium", INICIO, FIN, True, False),
    ]
    assert v[0]["nombre"] == "Lucía García"


def test_arranque_con_ficheros_sin_columna_op(spark):
    sin_op = lote(spark, [fila(CARGA)]).drop("Op")
    df = aplicar_scd2(spark, CLIENTES, dim_vacia(spark), sin_op)
    assert [resumen(f.asDict()) for f in df.collect()] == [("Standard", INICIO, FIN, True, False)]


# --- 2. La trampa: carga completa y CDC en el mismo lote -----------------------------------


def test_carga_completa_y_cdc_en_el_mismo_lote(spark):
    c981 = {**CLIENTE_17, "cliente_id": "C-981", "provincia": "Madrid"}
    c4001 = {**CLIENTE_17, "cliente_id": "C-4001", "provincia": "Lyon", "pais": "FR"}
    filas = [
        # Los cambios van primero a propósito: el orden del lote no debe importar
        fila(CAMBIO, "U", segmento="Premium"),
        fila(CAMBIO, "I", base=c4001),
        fila(CAMBIO, "D", base=c981),
        fila(CARGA),
        fila(CARGA, base=c981),
    ]
    por_cliente = {}
    for v in versiones(spark, filas):
        por_cliente.setdefault(v["cliente_id"], []).append(resumen(v))
    assert por_cliente == {
        "C-17": [("Standard", INICIO, DIA, False, False), ("Premium", DIA, FIN, True, False)],
        "C-4001": [("Standard", DIA, FIN, True, False)],
        "C-981": [("Standard", INICIO, DIA, False, True)],
    }


# --- 3. Solo SCD1 ------------------------------------------------------------------------


def test_cambio_solo_scd1(spark):
    v = versiones(spark, [fila(CARGA), fila(CAMBIO, "U", email="nuevo@ejemplo.com")])
    assert [resumen(x) for x in v] == [("Standard", INICIO, FIN, True, False)]
    assert v[0]["email"] == "nuevo@ejemplo.com"
    assert v[0]["ts_ultimo_cambio"].year == 2026


# --- 4. Mismo día --------------------------------------------------------------------------


def test_dos_cambios_el_mismo_dia(spark):
    v = versiones(
        spark,
        [
            fila(CARGA),
            fila(CAMBIO, "U", segmento="Premium"),
            fila("2026-10-28 18:00:00.000000", "U", segmento="Premium", provincia="Madrid"),
        ],
    )
    assert [(x["segmento"], x["provincia"], x["valid_from"], x["valid_to"]) for x in v] == [
        ("Standard", "Valencia", INICIO, DIA),
        ("Premium", "Madrid", DIA, FIN),
    ]


def test_scd1_el_mismo_dia_que_el_cambio_scd2(spark):
    v = versiones(
        spark,
        [
            fila(CARGA),
            fila(CAMBIO, "U", segmento="Premium"),
            fila("2026-10-28 18:00:00", "U", segmento="Premium", email="x"),
        ],
    )
    assert [(x["segmento"], x["email"]) for x in v][-1] == ("Premium", "x")
    assert len(v) == 2


def test_alta_y_baja_el_mismo_dia_y_nueva_alta(spark):
    c = {**CLIENTE_17, "cliente_id": "C-5000"}
    v = versiones(spark, [fila(CAMBIO, "I", base=c), fila("2026-10-28 18:00:00", "D", base=c)])
    assert [resumen(x) for x in v] == [("Standard", DIA, DIA, False, True)]
    v = versiones(
        spark,
        [
            fila(CAMBIO, "I", base=c),
            fila("2026-10-28 18:00:00", "D", base=c),
            fila("2026-10-28 19:00:00", "I", base=c),
        ],
    )
    assert [resumen(x) for x in v] == [("Standard", DIA, FIN, True, False)]


# --- 5. Vuelta al valor anterior -------------------------------------------------------------


def test_cliente_que_vuelve_a_su_segmento_anterior(spark):
    v = versiones(
        spark,
        [
            fila(CARGA),
            fila(CAMBIO, "U", segmento="Premium"),
            fila(OTRO_DIA, "U", segmento="Standard"),
        ],
    )
    assert [resumen(x) for x in v] == [
        ("Standard", INICIO, DIA, False, False),
        ("Premium", DIA, SIGUIENTE, False, False),
        ("Standard", SIGUIENTE, FIN, True, False),
    ]


# --- Ejecuciones sucesivas ---------------------------------------------------------------------


def test_segunda_ejecucion_parte_de_lo_que_ya_hay_en_silver(spark):
    primera = aplicar_scd2(spark, CLIENTES, dim_vacia(spark), lote(spark, [fila(CARGA)]))
    v = versiones(spark, [fila(CAMBIO, "U", segmento="Premium")], dim=primera)
    assert [resumen(x) for x in v] == [
        ("Standard", INICIO, DIA, False, False),
        ("Premium", DIA, FIN, True, False),
    ]


def test_recarga_completa_no_altera_lo_que_ya_existe(spark):
    primera = aplicar_scd2(spark, CLIENTES, dim_vacia(spark), lote(spark, [fila(CARGA)]))
    v = versiones(spark, [fila(OTRO_DIA, segmento="Premium")], dim=primera)
    assert [resumen(x) for x in v] == [("Standard", INICIO, FIN, True, False)]


def test_baja_de_una_clave_desconocida_no_crea_nada(spark):
    assert versiones(spark, [fila(CAMBIO, "D")]) == []


def test_alta_tras_una_baja_abre_otra_version(spark):
    v = versiones(spark, [fila(CARGA), fila(CAMBIO, "D"), fila(OTRO_DIA, "I")])
    assert [resumen(x) for x in v] == [
        ("Standard", INICIO, DIA, False, True),
        ("Standard", SIGUIENTE, FIN, True, False),
    ]


def test_productos_con_decimales(spark):
    lote_productos = spark.createDataFrame(
        [
            (
                "2026-10-28 17:20:00", "P-0412-ROJ-M", "0412", "Rojo", "M", "vestidos", "PV26",
                Decimal("39.95"), Decimal("15.74"),
            )
        ],
        "ts_commit string, producto_id string, modelo string, color string, talla string, familia string, "
        "temporada string, precio_catalogo decimal(8,2), coste_unitario decimal(8,2)",
    )
    v = aplicar_scd2(spark, PRODUCTOS, dim_vacia(spark, PRODUCTOS), lote_productos).collect()
    assert (v[0]["producto_id"], v[0]["valid_from"]) == ("P-0412-ROJ-M", INICIO)
    assert v[0]["precio_catalogo"] == Decimal("39.95")


# --- 6. Ventas -------------------------------------------------------------------------------


COLUMNAS_VENTA = (
    "event_id string, event_ts string, canal string, tienda_id string, ticket_id string, linea long, "
    "cliente_id string, producto_id string, unidades long, precio_unitario double, descuento double, "
    "moneda string, medio_pago string"
)


def venta(event_id="e1", tienda="ES-VLC-001", unidades=1, precio=39.95, descuento=0.0, moneda="EUR", cliente="C-1"):
    return (
        event_id, "2026-10-28T17:06:04.965Z", "TPV", tienda, "T-1", 1, cliente, "P-0412-ROJ-M",
        unidades, precio, descuento, moneda, "TARJETA",
    )  # fmt: skip


@pytest.fixture
def cambio(spark):
    return spark.createDataFrame(
        [
            ("EUR", Decimal("1.00000000")),
            ("USD", Decimal("0.92592593")),
            ("JPY", Decimal("0.00625000")),
            ("CNY", Decimal("0.12820513")),
        ],
        "moneda string, eur_por_unidad decimal(18,8)",
    )


def transformar(spark, cambio, filas):
    df = spark.createDataFrame(filas, COLUMNAS_VENTA)
    return {f["event_id"]: f for f in transformar_ventas(df, cambio).collect()}


def test_desduplica_por_event_id(spark, cambio):
    salida = transformar(spark, cambio, [venta("e1"), venta("e1"), venta("e2")])
    assert sorted(salida) == ["e1", "e2"]


def test_importes_a_eur_incluido_jpy_sin_decimales(spark, cambio):
    salida = transformar(
        spark,
        cambio,
        [
            venta("eur", unidades=2, descuento=10.0),
            venta("jpy", tienda="JP-TYO-001", precio=6392.0, descuento=1278.0, moneda="JPY"),
            venta("jpy2", tienda="JP-TYO-001", unidades=3, precio=6392.0, moneda="JPY"),
            venta("usd", tienda="US-NYC-001", precio=43.15, moneda="USD"),
            venta("cny", tienda="CN-SHA-001", precio=311.61, moneda="CNY"),
        ],
    )
    assert (salida["eur"]["importe_bruto"], salida["eur"]["descuento"]) == (Decimal("79.90"), Decimal("10.00"))
    # El descuento ya es el total de la línea: no se multiplica por unidades
    assert (salida["jpy"]["importe_bruto"], salida["jpy"]["descuento"]) == (Decimal("39.95"), Decimal("7.99"))
    assert salida["jpy2"]["importe_bruto"] == Decimal("119.85")
    assert salida["jpy"]["precio_unitario"] == Decimal("6392.00")  # en moneda local
    assert salida["usd"]["importe_bruto"] == Decimal("39.95")
    assert salida["cny"]["importe_bruto"] == Decimal("39.95")


def test_pais_de_tiendas_y_online(spark, cambio):
    salida = transformar(
        spark, cambio, [venta("a", tienda=" es-vlc-001 "), venta("b", tienda="ONL-JP", moneda="JPY", precio=6392.0)]
    )
    assert (salida["a"]["tienda_id"], salida["a"]["pais"]) == ("ES-VLC-001", "ES")
    assert (salida["b"]["tienda_id"], salida["b"]["pais"]) == ("ONL-JP", "JP")


def test_fecha_venta_en_utc(spark, cambio):
    salida = transformar(spark, cambio, [venta()])
    assert salida["e1"]["fecha_venta"].isoformat().startswith("2026-10-28")
    assert spark.conf.get("spark.sql.session.timeZone") == "UTC"


def test_moneda_desconocida_no_se_pierde_en_el_join(spark, cambio):
    salida = transformar(spark, cambio, [venta("x", moneda="GBP"), venta("y", cliente=None)])
    assert salida["x"]["importe_bruto"] is None  # Data Quality la manda a cuarentena
    assert salida["y"]["cliente_id"] is None


def test_columnas_ausentes_en_el_fichero(spark, cambio):
    df = spark.createDataFrame([venta()], COLUMNAS_VENTA).drop("cliente_id")
    assert transformar_ventas(df, cambio).collect()[0]["cliente_id"] is None


def test_cuarentena_conserva_las_columnas_de_bronze_como_texto(spark):
    malas = spark.createDataFrame([venta("m", unidades=0)], COLUMNAS_VENTA).selectExpr(
        "*", "array('ColumnValues unidades >= 1', 'otra') AS DataQualityRulesFail"
    )
    f = a_cuarentena(malas).collect()[0]
    assert (f["event_id"], f["unidades"], f["moneda"]) == ("m", "0", "EUR")
    assert f["motivo"] == "ColumnValues unidades >= 1; otra"
    assert f["fecha_carga"] is not None


# --- Control de calidad ------------------------------------------------------------------------


def test_control_de_calidad():
    reglas = [{"regla": "RowCount > 0", "resultado": "Passed", "motivo": None}]
    c = control_calidad(110, 95, 5, reglas)
    assert (c["filas_leidas"], c["filas_ok"], c["filas_cuarentena"], c["pct_cuarentena"]) == (110, 95, 5, 5.0)
    assert c["reglas"] == reglas and c["ts_fin"]
    assert fuente_rota(c) is False
    assert fuente_rota(control_calidad(10, 4, 6, [])) is True
    assert fuente_rota(control_calidad(10, 5, 5, [])) is False  # exactamente el 50 %: no


def test_control_sin_datos():
    assert control_calidad(0, 0, 0, [])["pct_cuarentena"] == 0.0
