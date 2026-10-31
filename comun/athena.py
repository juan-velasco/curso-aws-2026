"""Ejecución de SQL en Athena desde los scripts de apoyo (demos 3 y 4)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

ESTADOS_FINALES = {"SUCCEEDED", "FAILED", "CANCELLED"}
USD_POR_TB = 5.0


class ErrorAthena(RuntimeError):
    pass


@dataclass
class Resultado:
    sql: str
    columnas: list[str] = field(default_factory=list)
    filas: list[list[str | None]] = field(default_factory=list)
    bytes_escaneados: int = 0
    id_consulta: str = ""

    @property
    def coste_usd(self) -> float:
        return self.bytes_escaneados / 1e12 * USD_POR_TB

    @property
    def primera(self) -> dict[str, str | None]:
        """Primera fila como diccionario columna -> valor."""
        return dict(zip(self.columnas, self.filas[0]))


def sustituir(sql: str, valores: dict[str, str]) -> str:
    """Sustituye solo los marcadores indicados: ${anio} del DDL de bronze es de Athena."""
    for nombre, valor in valores.items():
        sql = sql.replace("${" + nombre + "}", valor)
    return sql


def separar_sentencias(texto: str) -> list[str]:
    """Separa un fichero en sentencias, sin hacer caso de los ; en comentarios, cadenas o $$ ... $$."""
    sentencias, actual = [], []
    i, en_cadena = 0, False
    while i < len(texto):
        c = texto[i]
        if not en_cadena and texto.startswith("$$", i):  # cuerpo de un procedimiento: va entero
            fin = texto.index("$$", i + 2) + 2
            actual.append(texto[i:fin])
            i = fin
            continue
        if en_cadena:
            en_cadena = c != "'"
        elif c == "'":
            en_cadena = True
        elif texto.startswith("--", i):
            fin = texto.find("\n", i)
            i = len(texto) if fin == -1 else fin
            continue
        elif c == ";":
            sentencias.append("".join(actual).strip())
            actual = []
            i += 1
            continue
        actual.append(c)
        i += 1
    sentencias.append("".join(actual).strip())
    return [s for s in sentencias if s]


def ejecutar(cliente, sql: str, workgroup: str = "curso", espera: float = 1.0) -> Resultado:
    """Lanza una sentencia, espera a que termine y devuelve filas y bytes escaneados."""
    id_consulta = cliente.start_query_execution(QueryString=sql, WorkGroup=workgroup)["QueryExecutionId"]
    while True:
        ejecucion = cliente.get_query_execution(QueryExecutionId=id_consulta)["QueryExecution"]
        estado = ejecucion["Status"]["State"]
        if estado in ESTADOS_FINALES:
            break
        time.sleep(espera)
    if estado != "SUCCEEDED":
        motivo = ejecucion["Status"].get("StateChangeReason", "sin detalle")
        raise ErrorAthena(f"{estado}: {motivo}\nSQL:\n{sql}")

    resultado = Resultado(
        sql=sql,
        id_consulta=id_consulta,
        bytes_escaneados=ejecucion.get("Statistics", {}).get("DataScannedInBytes", 0),
    )
    # Solo las consultas devuelven filas; en DDL y DML no hay nada que leer
    if ejecucion.get("StatementType") == "DML" and sql.lstrip().upper().startswith(("SELECT", "WITH")):
        paginas = cliente.get_paginator("get_query_results").paginate(QueryExecutionId=id_consulta)
        for n, pagina in enumerate(paginas):
            conjunto = pagina["ResultSet"]
            filas = [[d.get("VarCharValue") for d in fila["Data"]] for fila in conjunto["Rows"]]
            if n == 0:
                resultado.columnas = [c["Name"] for c in conjunto["ResultSetMetadata"]["ColumnInfo"]]
                filas = filas[1:]  # la primera fila repite los nombres de las columnas
            resultado.filas += filas
    return resultado


def formato_bytes(n: int) -> str:
    for unidad in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidad == "GB":
            return f"{n:.0f} {unidad}" if unidad == "B" else f"{n:.2f} {unidad}"
        n /= 1024
    return ""
