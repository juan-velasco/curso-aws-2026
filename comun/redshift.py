"""Ejecución de SQL en Redshift Serverless con la Data API (demo 4)."""

from __future__ import annotations

import time

ESTADOS_FINALES = {"FINISHED", "FAILED", "ABORTED"}


class ErrorRedshift(RuntimeError):
    pass


def ejecutar(cliente, sql: str, workgroup: str, secreto: str | None = None, database: str = "dev", espera: float = 1.0):
    """Lanza una sentencia, espera y devuelve (columnas, filas). Sin secreto, autentica con IAM."""
    extra = {"SecretArn": secreto} if secreto else {}
    id_sentencia = cliente.execute_statement(WorkgroupName=workgroup, Database=database, Sql=sql, **extra)["Id"]
    while True:
        estado = cliente.describe_statement(Id=id_sentencia)
        if estado["Status"] in ESTADOS_FINALES:
            break
        time.sleep(espera)
    if estado["Status"] != "FINISHED":
        raise ErrorRedshift(estado.get("Error", estado["Status"]))
    if not estado.get("HasResultSet"):
        return [], []

    columnas, filas, token = [], [], None
    while True:
        pagina = cliente.get_statement_result(Id=id_sentencia, **({"NextToken": token} if token else {}))
        columnas = [c["name"] for c in pagina["ColumnMetadata"]]
        filas += [[None if c.get("isNull") else next(iter(c.values())) for c in fila] for fila in pagina["Records"]]
        token = pagina.get("NextToken")
        if not token:
            return columnas, filas
