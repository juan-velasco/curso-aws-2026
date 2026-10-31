"""Transformaciones de bronze a silver: funciones puras, sin dependencias de Glue.

Los jobs (bronze_a_silver_*.py) leen y escriben; aquí solo se transforma, para
poder probarlo en local con PySpark (glue/tests/). Se sube a S3 y los jobs lo
cargan con --extra-py-files. Glue 5.0 usa Python 3.11.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    DateType,
    DecimalType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# --- Ventas --------------------------------------------------------------------------

COLUMNAS_BRONZE = {
    "event_id": "string",
    "event_ts": "string",
    "canal": "string",
    "tienda_id": "string",
    "ticket_id": "string",
    "linea": "int",
    "cliente_id": "string",
    "producto_id": "string",
    "unidades": "int",
    "precio_unitario": "double",
    "descuento": "double",
    "moneda": "string",
    "medio_pago": "string",
}

COLUMNAS_SILVER_VENTAS = [
    "event_id", "fecha_venta", "canal", "tienda_id", "ticket_id", "linea", "cliente_id", "producto_id",
    "unidades", "precio_unitario", "moneda", "importe_bruto", "descuento", "medio_pago", "pais", "fecha_carga",
]  # fmt: skip

UMBRAL_FUENTE_ROTA_PCT = 50.0


def con_columnas(df: DataFrame, columnas: dict[str, str]) -> DataFrame:
    """Añade las columnas ausentes y fija los tipos.

    Un fichero sin ningún cliente_id, por ejemplo, llega sin esa columna a la
    inferencia de esquema de JSON.
    """
    for nombre, tipo in columnas.items():
        columna = F.col(nombre) if nombre in df.columns else F.lit(None)
        df = df.withColumn(nombre, columna.cast(tipo))
    return df.select(*columnas)


def transformar_ventas(df: DataFrame, cambio: DataFrame) -> DataFrame:
    """De bronze a la forma de silver.ventas, sin filtrar: lo inválido lo separa Data Quality.

    - pais: los dos primeros caracteres de tienda_id, salvo en online (ONL-ES -> ES).
    - Importes a EUR. descuento ya es el total de la línea: no se multiplica por unidades.
    - El join con tipos de cambio es LEFT: una moneda desconocida debe llegar a Data
      Quality y acabar en cuarentena, no desaparecer en el join.
    """
    eur = F.col("eur_por_unidad")
    precio = F.col("precio_unitario").cast("decimal(12,2)")
    return (
        con_columnas(df, COLUMNAS_BRONZE)
        .withColumn("tienda_id", F.upper(F.trim("tienda_id")))
        .withColumn("fecha_venta", F.to_timestamp("event_ts"))
        .withColumn(
            "pais",
            F.when(F.col("tienda_id").startswith("ONL-"), F.substring("tienda_id", 5, 2)).otherwise(
                F.substring("tienda_id", 1, 2)
            ),
        )
        .dropDuplicates(["event_id"])
        .join(F.broadcast(cambio.select("moneda", "eur_por_unidad")), "moneda", "left")
        .withColumn("precio_unitario", precio)
        .withColumn("importe_bruto", (F.col("unidades") * precio * eur).cast("decimal(12,2)"))
        .withColumn("descuento", (F.col("descuento").cast("decimal(12,2)") * eur).cast("decimal(12,2)"))
        .withColumn("fecha_carga", F.current_timestamp())
        .select(*COLUMNAS_SILVER_VENTAS, "event_ts")
    )


def a_cuarentena(malas: DataFrame) -> DataFrame:
    """Filas rechazadas: columnas de bronze como string, el motivo y la fecha de carga."""
    columnas = [F.col(c).cast("string").alias(c) for c in COLUMNAS_BRONZE]
    return malas.select(
        *columnas,
        F.concat_ws("; ", "DataQualityRulesFail").alias("motivo"),
        F.current_timestamp().alias("fecha_carga"),
    )


def control_calidad(filas_leidas: int, filas_ok: int, filas_cuarentena: int, reglas: list[dict]) -> dict:
    """Contenido de control/calidad/ventas/ultima.json, que lee la máquina de estados."""
    evaluadas = filas_ok + filas_cuarentena
    pct = round(filas_cuarentena / evaluadas * 100, 2) if evaluadas else 0.0
    return {
        "filas_leidas": filas_leidas,
        "filas_ok": filas_ok,
        "filas_cuarentena": filas_cuarentena,
        "pct_cuarentena": pct,
        "reglas": reglas,
        "ts_fin": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def fuente_rota(control: dict) -> bool:
    """Más de la mitad de las filas rechazadas: el problema es la fuente, no unas filas."""
    return control["pct_cuarentena"] > UMBRAL_FUENTE_ROTA_PCT


# --- Maestros: SCD2 ----------------------------------------------------------------------

INICIO_DE_LOS_TIEMPOS = date(1900, 1, 1)
FIN_DE_LOS_TIEMPOS = date(9999, 12, 31)
COLUMNAS_VIGENCIA = [
    StructField("valid_from", DateType()),
    StructField("valid_to", DateType()),
    StructField("is_current", BooleanType()),
    StructField("es_baja", BooleanType()),
    StructField("ts_ultimo_cambio", TimestampType()),
]


@dataclass(frozen=True)
class Maestro:
    """Una dimensión: su clave y qué columnas abren versión (SCD2) y cuáles se sobrescriben (SCD1)."""

    tabla: str
    clave: str
    scd2: tuple[str, ...]
    scd1: tuple[str, ...]
    fijas: tuple[str, ...]  # se toman del primer registro y no cambian
    tipos: dict  # tipos de Spark de las columnas de negocio

    @property
    def esquema(self) -> StructType:
        negocio = [self.clave, *self.tipos]
        return StructType([StructField(c, self.tipos.get(c, StringType())) for c in negocio] + COLUMNAS_VIGENCIA)


CLIENTES = Maestro(
    tabla="dim_cliente",
    clave="cliente_id",
    scd2=("segmento", "provincia", "pais"),
    scd1=("nombre", "email", "telefono"),
    fijas=("fecha_alta",),
    tipos={
        "nombre": StringType(),
        "email": StringType(),
        "telefono": StringType(),
        "segmento": StringType(),
        "provincia": StringType(),
        "pais": StringType(),
        "fecha_alta": DateType(),
    },
)

PRODUCTOS = Maestro(
    tabla="dim_producto",
    clave="producto_id",
    scd2=("familia", "temporada"),
    scd1=("precio_catalogo", "coste_unitario", "modelo", "color", "talla"),
    fijas=(),
    tipos={
        "modelo": StringType(),
        "color": StringType(),
        "talla": StringType(),
        "familia": StringType(),
        "temporada": StringType(),
        "precio_catalogo": DecimalType(8, 2),
        "coste_unitario": DecimalType(8, 2),
    },
)


def _abrir(versiones: list[dict], maestro: Maestro, evento: dict, valid_from: date) -> None:
    """Abre la versión vigente. Si ya hay una que empieza ese día, la reutiliza: ninguna dura cero días."""
    nueva = {c: evento[c] for c in (maestro.clave, *maestro.scd2, *maestro.scd1, *maestro.fijas)}
    nueva |= {
        "valid_from": valid_from,
        "valid_to": FIN_DE_LOS_TIEMPOS,
        "is_current": True,
        "es_baja": False,
        "ts_ultimo_cambio": evento["ts"],
    }
    if versiones and versiones[-1]["valid_from"] == valid_from:
        versiones[-1] = nueva
    else:
        versiones.append(nueva)


def _aplicar_evento(versiones: list[dict], maestro: Maestro, evento: dict) -> None:
    """Aplica un evento a las versiones de una clave, ordenadas por valid_from."""
    op, fecha = evento["op"], evento["fecha_cambio"]
    vigente = versiones[-1] if versiones and versiones[-1]["is_current"] else None

    if op is None:  # carga completa: solo crea la primera versión de lo que aún no existe
        if not versiones:
            _abrir(versiones, maestro, evento, INICIO_DE_LOS_TIEMPOS)
    elif op == "D":
        if vigente:
            vigente |= {"valid_to": fecha, "is_current": False, "es_baja": True, "ts_ultimo_cambio": evento["ts"]}
    elif vigente is None:  # I, o U de una clave desconocida o dada de baja
        _abrir(versiones, maestro, evento, fecha)
    elif any(vigente[c] != evento[c] for c in maestro.scd2):
        if vigente["valid_from"] == fecha:  # mismo día: se corrige la vigente
            _abrir(versiones, maestro, evento, fecha)
        else:
            vigente |= {"valid_to": fecha, "is_current": False, "ts_ultimo_cambio": evento["ts"]}
            _abrir(versiones, maestro, evento, fecha)
    else:  # solo cambios SCD1: se sobrescribe la vigente
        vigente |= {c: evento[c] for c in maestro.scd1}
        vigente["ts_ultimo_cambio"] = evento["ts"]


def calcular_versiones(maestro: Maestro, actuales: list[dict], eventos: list[dict]) -> list[dict]:
    """Versiones resultantes de aplicar los eventos sobre las versiones existentes.

    La trampa de la primera ejecución es que llegan juntos la carga completa y los
    cambios: con "último cambio por clave", C-17 acabaría con una sola versión Premium
    desde 1900. Por eso se recorre la historia clave a clave, primero la carga completa
    (op nulo) y después los cambios en orden de ts_commit, y cada evento se aplica como
    lo haría una ejecución separada. Las versiones resultantes se fusionan con MERGE por
    clave + valid_from.

    Devuelve solo las versiones de las claves con eventos.
    """
    por_clave: dict[str, list[dict]] = {}
    for evento in sorted(eventos, key=lambda e: (e["op"] is not None, e["ts"])):
        por_clave.setdefault(evento[maestro.clave], []).append(evento)

    existentes: dict[str, list[dict]] = {}
    for fila in sorted(actuales, key=lambda f: f["valid_from"]):
        existentes.setdefault(fila[maestro.clave], []).append(dict(fila))

    resultado = []
    for clave, de_la_clave in por_clave.items():
        versiones = existentes.get(clave, [])
        for evento in de_la_clave:
            _aplicar_evento(versiones, maestro, evento)
        resultado += versiones
    return resultado


def preparar_eventos(df: DataFrame, maestro: Maestro) -> DataFrame:
    """De los Parquet de DMS a eventos: Op (ausente en la carga completa) y ts_commit convertido.

    ts_commit es un string en UTC: los jobs fijan spark.sql.session.timeZone = UTC.
    """
    op = F.col("Op") if "Op" in df.columns else F.lit(None).cast("string")
    negocio = [F.col(c).cast(t) for c, t in maestro.tipos.items()]
    return df.select(
        op.alias("op"),
        F.col(maestro.clave),
        *negocio,
        F.to_timestamp("ts_commit").alias("ts"),
        F.to_date(F.to_timestamp("ts_commit")).alias("fecha_cambio"),
    )


def aplicar_scd2(spark: SparkSession, maestro: Maestro, dim: DataFrame, lote: DataFrame) -> DataFrame:
    """Versiones a fusionar en la dimensión.

    Se calcula en el driver con Python: son miles de filas y la lógica se lee mejor
    como una máquina de estados que como funciones de ventana. Con millones de claves
    habría que repartirlo con groupBy + applyInPandas.
    """
    eventos = [fila.asDict() for fila in preparar_eventos(lote, maestro).collect()]
    claves = {e[maestro.clave] for e in eventos}
    actuales = [fila.asDict() for fila in dim.collect() if fila[maestro.clave] in claves]
    versiones = calcular_versiones(maestro, actuales, eventos)
    return spark.createDataFrame(
        [tuple(v[c.name] for c in maestro.esquema) for v in versiones], maestro.esquema
    )

