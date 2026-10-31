"""Tests del backfill de ventas contra S3 simulado (moto)."""

import gzip
import json
import os
import re
from collections import Counter
from datetime import date, timedelta

import boto3
import pytest
from moto import mock_aws

os.environ.setdefault("AWS_REGION", "eu-west-1")
os.environ.setdefault("FIREHOSE_STREAM", "hp-retail-ventas")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

from app.main import Venta  # noqa: E402
from backfill_ventas import generar_dia, rellenar  # noqa: E402
from comun import eventos as ev  # noqa: E402
from comun import maestros  # noqa: E402

BUCKET = "lago"
LABORABLE = date(2026, 10, 7)  # miércoles, OI, sin rebajas


@pytest.fixture
def s3():
    with mock_aws():
        cliente = boto3.client("s3", region_name="eu-west-1")
        cliente.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"})
        yield cliente


def leer_todo(s3, prefijo="bronze/ventas/"):
    respuesta = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefijo)
    salida = {}
    for o in respuesta.get("Contents", []):
        cuerpo = s3.get_object(Bucket=BUCKET, Key=o["Key"])["Body"].read()
        salida[o["Key"]] = [json.loads(linea) for linea in gzip.decompress(cuerpo).decode().splitlines()]
    return salida


def test_eventos_validan_contra_el_contrato_de_la_api():
    eventos = generar_dia(LABORABLE, 300, 2)
    for e in eventos:
        Venta.model_validate(e)
        assert e["event_ts"].startswith("2026-10-07T")
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", e["event_ts"])


def test_determinista_y_sin_clientes_fuera_de_la_semilla():
    a, b = generar_dia(LABORABLE, 300, 2), generar_dia(LABORABLE, 300, 2)
    assert a == b
    assert generar_dia(LABORABLE + timedelta(days=1), 300, 2) != a
    clientes = maestros.indice_clientes()
    assert all(e["cliente_id"] is None or e["cliente_id"] in clientes for e in a)


def test_duplicados():
    eventos = generar_dia(LABORABLE, 3000, 5)
    distintos = len({e["event_id"] for e in eventos})
    pct = (len(eventos) - distintos) / distintos * 100
    assert 3 < pct < 7
    assert len({e["event_id"] for e in generar_dia(LABORABLE, 3000, 0)}) == len(generar_dia(LABORABLE, 3000, 0))


def test_factores_de_volumen():
    assert ev.eventos_del_dia(LABORABLE, 1000) == 1000
    assert ev.eventos_del_dia(date(2026, 10, 10), 1000) == 1300  # sábado
    assert ev.eventos_del_dia(date(2026, 7, 8), 1000) == 1600  # miércoles en rebajas
    assert ev.eventos_del_dia(date(2026, 7, 11), 1000) == 2080  # sábado en rebajas
    # El volumen generado sigue al objetivo (el número de líneas por ticket es aleatorio)
    for fecha in (LABORABLE, date(2026, 7, 11)):
        objetivo = ev.eventos_del_dia(fecha, 3000)
        assert abs(len(generar_dia(fecha, 3000, 0)) - objetivo) < objetivo * 0.05


def test_estacionalidad_por_familia():
    def cuota(fecha, familia):
        productos = maestros.indice_productos()
        eventos = generar_dia(fecha, 6000, 0)
        return Counter(productos[e["producto_id"]].familia for e in eventos)[familia] / len(eventos)

    agosto, noviembre = date(2026, 8, 12), date(2026, 11, 11)
    assert cuota(noviembre, "abrigos") > 1.5 * cuota(agosto, "abrigos")
    assert cuota(noviembre, "punto") > 1.5 * cuota(agosto, "punto")
    assert cuota(agosto, "baño") > 1.5 * cuota(noviembre, "baño")


def test_rellenar_escribe_en_el_formato_de_firehose(s3):
    totales = rellenar(s3, BUCKET, date(2026, 10, 2), 2, 200, 2)
    assert totales["dias_escritos"] == 2
    ficheros = leer_todo(s3)
    assert set(ficheros) == {
        "bronze/ventas/anio=2026/mes=10/dia=01/backfill-2026-10-01-000.json.gz",
        "bronze/ventas/anio=2026/mes=10/dia=02/backfill-2026-10-02-000.json.gz",
    }
    assert sum(len(v) for v in ficheros.values()) == totales["eventos"]
    cabecera = s3.head_object(Bucket=BUCKET, Key=next(iter(ficheros)))
    assert cabecera["ContentEncoding"] == "gzip"


def test_trocea_en_varios_ficheros(s3):
    rellenar(s3, BUCKET, LABORABLE, 1, 5000, 0)
    ficheros = leer_todo(s3)
    assert sorted(k.rsplit("-", 1)[1] for k in ficheros) == ["000.json.gz", "001.json.gz", "002.json.gz"]


def test_idempotente_y_no_toca_firehose(s3):
    firehose = "bronze/ventas/anio=2026/mes=10/dia=07/hp-retail-ventas-1-2026-10-07-17-08-59-x.json.gz"
    s3.put_object(Bucket=BUCKET, Key=firehose, Body=gzip.compress(b'{"a": 1}\n'))

    primera = rellenar(s3, BUCKET, LABORABLE, 1, 200, 2)
    assert primera["dias_escritos"] == 1

    segunda = rellenar(s3, BUCKET, LABORABLE, 1, 200, 2)
    assert (segunda["dias_escritos"], segunda["dias_saltados"], segunda["eventos"]) == (0, 1, 0)

    forzada = rellenar(s3, BUCKET, LABORABLE, 1, 100, 2, forzar=True)
    assert forzada["dias_escritos"] == 1
    ficheros = leer_todo(s3)
    assert ficheros[firehose] == [{"a": 1}]
    claves_backfill = [k for k in ficheros if "backfill-" in k]
    assert len(claves_backfill) == 1
    assert len(ficheros[claves_backfill[0]]) == forzada["eventos"]
