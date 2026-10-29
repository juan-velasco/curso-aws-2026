"""API de ventas: recibe lotes de ventas del TPV y los envía a Amazon Data Firehose."""

import logging
import os
import time
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_serializer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("api-ventas")

# Sin región, boto3 no puede crear el cliente: mejor fallar al arrancar con un mensaje claro
REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
if not REGION:
    raise RuntimeError("Falta la región de AWS: define AWS_REGION (o AWS_DEFAULT_REGION), p. ej. eu-west-1")

app = FastAPI(title="API de ventas")
fh = boto3.client("firehose", region_name=REGION)
STREAM = os.environ["FIREHOSE_STREAM"]

MAX_LOTE = 500  # límite de registros de PutRecordBatch


class Venta(BaseModel):
    event_id: UUID
    event_ts: datetime
    canal: str
    tienda_id: str
    ticket_id: str
    linea: int = Field(ge=1)
    cliente_id: str | None = None
    producto_id: str
    unidades: int = Field(ge=1)
    precio_unitario: float = Field(gt=0)
    descuento: float = Field(ge=0)
    moneda: str = Field(min_length=3, max_length=3)
    medio_pago: str

    @field_serializer("event_ts", when_used="json")
    def ts_contrato(self, ts: datetime) -> str:
        # En bronze, el formato del contrato: UTC con milisegundos y sufijo Z
        ts = ts.astimezone(UTC) if ts.tzinfo else ts.replace(tzinfo=UTC)
        return ts.isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EnvioIncompleto(Exception):
    def __init__(self, pendientes: int, total: int):
        super().__init__(f"{pendientes} registros sin enviar")
        self.pendientes = pendientes
        self.total = total


def enviar(ventas: list[Venta]) -> int:
    records = [{"Data": (v.model_dump_json() + "\n").encode()}
               for v in ventas]
    for intento in range(5):
        resp = fh.put_record_batch(
            DeliveryStreamName=STREAM, Records=records)
        if resp["FailedPutCount"] == 0:
            log.info("Lote recibido: %d registros, %d enviados, %d reintentos",
                     len(ventas), len(ventas), intento)
            return len(ventas)
        # reintentar solo los registros que fallaron
        records = [r for r, res in
                   zip(records, resp["RequestResponses"])
                   if "ErrorCode" in res]
        time.sleep(0.2 * 2 ** intento)
    log.error("Lote recibido: %d registros, %d enviados, %d sin enviar tras 5 intentos",
              len(ventas), len(ventas) - len(records), len(records))
    raise EnvioIncompleto(len(records), len(ventas))


@app.exception_handler(EnvioIncompleto)
def envio_incompleto(request: Request, exc: EnvioIncompleto):
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc), "pendientes": exc.pendientes, "recibidos": exc.total},
    )


@app.exception_handler(ClientError)
@app.exception_handler(BotoCoreError)
def error_aws(request: Request, exc: Exception):
    # Credenciales caducadas, stream inexistente, permisos...: el cliente puede reintentar
    log.error("Error llamando a Firehose: %s", exc)
    return JSONResponse(status_code=503, content={"detail": f"Error enviando a Firehose: {exc}"})


@app.post("/ventas/lote", status_code=202)
def recibir(lote: Annotated[list[Venta], Field(min_length=1, max_length=MAX_LOTE)]):
    return {"enviados": enviar(lote)}


@app.get("/health")
def health():
    return {"status": "ok"}
