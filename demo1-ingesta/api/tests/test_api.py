"""Tests de la API sin AWS: Firehose se simula con botocore.stub.Stubber."""

import json
import uuid

import pytest
from botocore.stub import ANY, Stubber
from fastapi.testclient import TestClient

from app import main

EVENTO = {
    "event_id": "7f3c2a9e-5b1d-4c8e-9a0f-2d6e8b1c4a77",
    "event_ts": "2026-10-24T10:15:32.481Z",
    "canal": "TPV",
    "tienda_id": "ES-VLC-003",
    "ticket_id": "T-20261024-003-000187",
    "linea": 2,
    "cliente_id": "C-17",
    "producto_id": "P-0412-ROJ-M",
    "unidades": 1,
    "precio_unitario": 39.95,
    "descuento": 8.00,
    "moneda": "EUR",
    "medio_pago": "TARJETA",
}


def evento(**cambios):
    return {**EVENTO, "event_id": str(uuid.uuid4()), **cambios}


def respuesta_ok(n):
    return {
        "FailedPutCount": 0,
        "Encrypted": False,
        "RequestResponses": [{"RecordId": f"r{i}"} for i in range(n)],
    }


@pytest.fixture
def cliente():
    return TestClient(main.app)


@pytest.fixture
def enviados():
    """Lista de los `Records` de cada llamada a PutRecordBatch."""
    llamadas = []

    def capturar(params, **kwargs):
        llamadas.append(params["Records"])

    evento = "before-parameter-build.firehose.PutRecordBatch"
    main.fh.meta.events.register(evento, capturar)
    yield llamadas
    main.fh.meta.events.unregister(evento, capturar)


@pytest.fixture
def firehose(monkeypatch):
    monkeypatch.setattr(main.time, "sleep", lambda s: None)
    with Stubber(main.fh) as stub:
        yield stub
        stub.assert_no_pending_responses()


def test_health(cliente):
    assert cliente.get("/health").json() == {"status": "ok"}


def test_evento_valido_202(cliente, firehose):
    firehose.add_response(
        "put_record_batch",
        respuesta_ok(1),
        {"DeliveryStreamName": "hp-retail-ventas", "Records": ANY},
    )
    r = cliente.post("/ventas/lote", json=[EVENTO])
    assert r.status_code == 202
    assert r.json() == {"enviados": 1}


def test_registro_en_json_lines(cliente, firehose, enviados):
    """Cada registro es un JSON terminado en salto de línea (JSON Lines en bronze)."""
    firehose.add_response("put_record_batch", respuesta_ok(2))
    assert cliente.post("/ventas/lote", json=[evento(), evento()]).status_code == 202
    assert len(enviados[0]) == 2
    for record in enviados[0]:
        assert record["Data"].endswith(b"\n")
        assert json.loads(record["Data"])["tienda_id"] == "ES-VLC-003"


def test_event_ts_con_formato_del_contrato():
    assert main.Venta(**EVENTO).model_dump()["event_ts"].isoformat() == "2026-10-24T10:15:32.481000+00:00"
    assert json.loads(main.Venta(**EVENTO).model_dump_json())["event_ts"] == "2026-10-24T10:15:32.481Z"
    otro = main.Venta(**{**EVENTO, "event_ts": "2026-10-24T12:15:32.4+02:00"})
    assert json.loads(otro.model_dump_json())["event_ts"] == "2026-10-24T10:15:32.400Z"


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("event_id", "no-es-uuid"),
        ("unidades", 0),
        ("precio_unitario", -1.0),
        ("moneda", "EU"),
    ],
)
def test_evento_invalido_422(cliente, firehose, campo, valor):
    r = cliente.post("/ventas/lote", json=[evento(**{campo: valor})])
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"][-1] == campo


def test_lote_vacio_422(cliente, firehose):
    assert cliente.post("/ventas/lote", json=[]).status_code == 422


def test_mas_de_500_registros_422(cliente, firehose):
    r = cliente.post("/ventas/lote", json=[evento() for _ in range(501)])
    assert r.status_code == 422
    assert r.json()["detail"][0]["type"] == "too_long"


def test_500_registros_202(cliente, firehose):
    firehose.add_response("put_record_batch", respuesta_ok(500))
    r = cliente.post("/ventas/lote", json=[evento() for _ in range(500)])
    assert r.status_code == 202
    assert r.json() == {"enviados": 500}


def test_reintenta_solo_los_fallidos(cliente, firehose, enviados):
    lote = [evento() for _ in range(3)]
    firehose.add_response(
        "put_record_batch",
        {
            "FailedPutCount": 1,
            "RequestResponses": [
                {"RecordId": "r0"},
                {"ErrorCode": "ServiceUnavailableException", "ErrorMessage": "Slow down."},
                {"RecordId": "r2"},
            ],
        },
    )
    firehose.add_response("put_record_batch", respuesta_ok(1))

    r = cliente.post("/ventas/lote", json=lote)

    assert r.status_code == 202
    assert r.json() == {"enviados": 3}
    assert [len(x) for x in enviados] == [3, 1]  # el reintento lleva solo el fallido
    assert json.loads(enviados[1][0]["Data"])["event_id"] == lote[1]["event_id"]


def test_fallos_persistentes_503(cliente, firehose):
    fallo = {
        "FailedPutCount": 2,
        "RequestResponses": [
            {"RecordId": "r0"},
            {"ErrorCode": "ServiceUnavailableException", "ErrorMessage": "Slow down."},
            {"ErrorCode": "ServiceUnavailableException", "ErrorMessage": "Slow down."},
        ],
    }
    fallo_2 = {"FailedPutCount": 2, "RequestResponses": fallo["RequestResponses"][1:]}
    firehose.add_response("put_record_batch", fallo)
    for _ in range(4):
        firehose.add_response("put_record_batch", fallo_2)

    r = cliente.post("/ventas/lote", json=[evento() for _ in range(3)])
    assert r.status_code == 503
    assert r.json()["pendientes"] == 2


def test_error_de_aws_503(cliente, firehose):
    firehose.add_client_error("put_record_batch", "ResourceNotFoundException", "Stream not found")
    r = cliente.post("/ventas/lote", json=[evento()])
    assert r.status_code == 503
    assert "ResourceNotFoundException" in r.json()["detail"]
