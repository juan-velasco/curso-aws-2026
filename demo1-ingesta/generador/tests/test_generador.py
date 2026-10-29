"""Tests del generador: eventos válidos según el modelo de la API y prueba
de extremo a extremo API + generador con Firehose simulado (moto)."""

import json
import os
import random
import re
from collections import Counter

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from pydantic import ValidationError

from comun import maestros

# La API lee la región y el stream al importarse
os.environ.setdefault("AWS_REGION", "eu-west-1")
os.environ.setdefault("FIREHOSE_STREAM", "hp-retail-ventas")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

from app.main import Venta  # noqa: E402
from generador import Config, FabricaVentas, Generador  # noqa: E402


@pytest.fixture
def fabrica():
    return FabricaVentas(random.Random(1))


@pytest.fixture
def eventos(fabrica):
    return [e for _ in range(2000) for e in fabrica.ticket()]


def test_eventos_validan_contra_el_modelo_de_la_api(eventos):
    for e in eventos:
        Venta.model_validate(e)


def test_contrato_del_evento(eventos):
    tiendas = {t.tienda_id: t for t in maestros.tiendas()}
    clientes = maestros.indice_clientes()
    productos = maestros.indice_productos()
    for e in eventos:
        assert list(e) == [
            "event_id", "event_ts", "canal", "tienda_id", "ticket_id", "linea", "cliente_id",
            "producto_id", "unidades", "precio_unitario", "descuento", "moneda", "medio_pago",
        ]
        tienda = tiendas[e["tienda_id"]]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", e["event_ts"])
        assert re.fullmatch(rf"T-{e['event_ts'][:10].replace('-', '')}-{tienda.numero}-\d{{6}}", e["ticket_id"])
        assert e["moneda"] == tienda.moneda
        assert e["cliente_id"] is None or clientes[e["cliente_id"]].pais == tienda.pais
        producto = productos[e["producto_id"]]
        assert e["precio_unitario"] == producto.precio_en(tienda.moneda)
        assert 0 <= e["descuento"] <= e["precio_unitario"] * e["unidades"]
        if tienda.es_online:
            assert e["canal"] in ("WEB", "APP") and e["medio_pago"] in ("TARJETA", "PAYPAL")
        else:
            assert e["canal"] == "TPV" and e["medio_pago"] in ("TARJETA", "EFECTIVO", "MOVIL")


def test_lineas_de_ticket(eventos):
    tickets = {}
    for e in eventos:
        tickets.setdefault((e["tienda_id"], e["ticket_id"]), []).append(e)
    for lineas in tickets.values():
        assert [e["linea"] for e in lineas] == list(range(1, len(lineas) + 1))
        assert 1 <= len(lineas) <= 4
        assert len({(e["event_ts"], e["cliente_id"], e["medio_pago"]) for e in lineas}) == 1
    sin_cliente = sum(v[0]["cliente_id"] is None for v in tickets.values()) / len(tickets)
    assert 0.25 < sin_cliente < 0.35
    unidades = Counter(e["unidades"] for e in eventos)
    assert unidades[1] > 0.8 * len(eventos)
    con_descuento = sum(e["descuento"] > 0 for e in eventos) / len(eventos)
    assert 0.1 < con_descuento < 0.3


def test_invalidos_no_validan(fabrica):
    for _ in range(50):
        with pytest.raises(ValidationError):
            Venta.model_validate(fabrica.invalido(fabrica.ticket()[0]))


def test_modo_pico():
    assert Config(eventos_por_segundo=1, modo="pico").ritmo == 10
    assert Config(eventos_por_segundo=1).ritmo == 1


def test_config_desde_entorno(monkeypatch):
    monkeypatch.setenv("MODO", "PICO")
    monkeypatch.setenv("TAM_LOTE", "50")
    c = Config.desde_entorno()
    assert (c.api_url, c.modo, c.tam_lote, c.duracion_min) == ("http://api:8000", "pico", 50, 10)
    monkeypatch.setenv("TAM_LOTE", "501")
    with pytest.raises(SystemExit):
        Config.desde_entorno()


@mock_aws
def test_api_y_generador_con_firehose_simulado(tmp_path, monkeypatch):
    """Extremo a extremo: generador -> API -> Firehose (moto) -> S3 (moto)."""
    from app import main

    region = os.environ["AWS_REGION"]
    s3 = boto3.client("s3", region_name=region)
    s3.create_bucket(Bucket="lago", CreateBucketConfiguration={"LocationConstraint": region})
    monkeypatch.setattr(main, "fh", boto3.client("firehose", region_name=region))  # cliente dentro del mock
    main.fh.create_delivery_stream(
        DeliveryStreamName="hp-retail-ventas",
        DeliveryStreamType="DirectPut",
        ExtendedS3DestinationConfiguration={
            "RoleARN": "arn:aws:iam::123456789012:role/firehose",
            "BucketARN": "arn:aws:s3:::lago",
            "Prefix": "bronze/ventas/",
        },
    )

    config = Config(
        eventos_por_segundo=40, duracion_min=0.05, tam_lote=25,
        duplicados_pct=10, invalidos_pct=5, salida=tmp_path,
    )
    generador = Generador(config, cliente=TestClient(main.app), rng=random.Random(7))
    resumen = generador.ejecutar()
    generador.guardar_resumen()

    assert resumen.eventos_generados >= 100
    assert resumen.eventos_perdidos == 0
    assert resumen.eventos_enviados == resumen.eventos_generados + resumen.duplicados_enviados
    assert resumen.eventos_aceptados == resumen.eventos_enviados
    assert resumen.duplicados_aceptados == resumen.duplicados_enviados > 0
    assert resumen.invalidos_rechazados == resumen.invalidos_enviados > 0

    # moto escribe cada registro en S3: lo que hay en bronze cuadra con el resumen
    lineas = []
    for obj in s3.list_objects_v2(Bucket="lago", Prefix="bronze/ventas/")["Contents"]:
        lineas += s3.get_object(Bucket="lago", Key=obj["Key"])["Body"].read().decode().splitlines()
    eventos = [json.loads(linea) for linea in lineas if linea]
    assert len(eventos) == resumen.eventos_aceptados
    assert len({e["event_id"] for e in eventos}) == resumen.eventos_aceptados - resumen.duplicados_aceptados

    guardado = json.loads((tmp_path / "resumen.json").read_text())
    assert guardado["eventos_aceptados"] == resumen.eventos_aceptados
