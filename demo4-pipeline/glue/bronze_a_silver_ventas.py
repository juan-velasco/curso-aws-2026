"""Job de Glue: ventas de bronze a silver.ventas (Iceberg) con Data Quality.

Lee los ficheros nuevos de bronze/ventas/ (bookmarks), desduplica, pasa los importes
a EUR, separa con Data Quality lo válido de la cuarentena y deja el resultado en
control/calidad/ventas/ultima.json para la máquina de estados.
"""

import json
import sys

import boto3
from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame
from awsglue.job import Job
from awsglue.transforms import SelectFromCollection
from awsglue.utils import getResolvedOptions
from awsgluedq.transforms import EvaluateDataQuality
from pyspark.context import SparkContext
from pyspark.sql import functions as F

from transformaciones import (
    COLUMNAS_BRONZE,
    COLUMNAS_SILVER_VENTAS,
    a_cuarentena,
    con_columnas,
    control_calidad,
    fuente_rota,
    transformar_ventas,
)

CLAVE_CONTROL = "control/calidad/ventas/ultima.json"

REGLAS_FILA = """Rules = [
  RowCount > 0,
  IsComplete "event_id",
  IsUnique "event_id",
  IsComplete "fecha_venta",
  IsComplete "producto_id",
  ColumnValues "unidades" >= 1,
  ColumnValues "moneda" in ["EUR","USD","JPY","CNY"]
]"""

# No es crítica: el histórico la incumple por diseño. Se evalúa aparte para que no
# mande filas antiguas a cuarentena; su resultado solo va al control.
REGLA_FRESCURA = """Rules = [
  DataFreshness "fecha_venta" <= 24 hours
]"""

args = getResolvedOptions(sys.argv, ["JOB_NAME", "BUCKET", "FORZAR_FALLO"])
glue = GlueContext(SparkContext())
spark = glue.spark_session
spark.conf.set("spark.sql.session.timeZone", "UTC")
job = Job(glue)
job.init(args["JOB_NAME"], args)

if args["FORZAR_FALLO"].lower() == "true":
    raise RuntimeError("FORZAR_FALLO = true: fallo provocado para la demo")


def evaluar(dyf, reglas, contexto):
    return EvaluateDataQuality().process_rows(
        frame=dyf,
        ruleset=reglas,
        publishing_options={
            "dataQualityEvaluationContext": contexto,
            "enableDataQualityCloudWatchMetrics": True,
            "enableDataQualityResultsPublishing": True,
        },
    )


def resultados_de_reglas(dq):
    filas = SelectFromCollection.apply(dq, key="ruleOutcomes").toDF().collect()
    return [{"regla": f["Rule"], "resultado": f["Outcome"], "motivo": f["FailureReason"]} for f in filas]


def escribir_control(control):
    boto3.client("s3").put_object(
        Bucket=args["BUCKET"],
        Key=CLAVE_CONTROL,
        Body=json.dumps(control, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )


def main():
    # 1. Leer bronze directamente de S3 (solo ficheros nuevos)
    dyf = glue.create_dynamic_frame.from_options(
        connection_type="s3",
        format="json",
        connection_options={"paths": [f"s3://{args['BUCKET']}/bronze/ventas/"], "recurse": True},
        transformation_ctx="bronze_ventas",  # bookmark
    )
    bronze = dyf.toDF().cache()
    filas_leidas = bronze.count()
    print(f"Filas leídas de bronze: {filas_leidas}")

    if filas_leidas == 0:
        # Sin ficheros nuevos no es un fallo: el generador puede estar parado
        escribir_control(control_calidad(0, 0, 0, []))
        job.commit()
        return  # sys.exit(0) no sirve: Glue lo marca como FAILED ("SystemExit: 0")

    # 2. Transformar
    cambio = spark.table("glue_catalog.silver.tipos_cambio")
    ventas = transformar_ventas(bronze, cambio).cache()

    # 3. Data Quality: filas válidas y cuarentena
    dyf_limpio = DynamicFrame.fromDF(ventas, glue, "ventas")
    dq = evaluar(dyf_limpio, REGLAS_FILA, "silver_ventas")
    filas = SelectFromCollection.apply(dq, key="rowLevelOutcomes").toDF().cache()
    ok = filas.filter("DataQualityEvaluationResult = 'Passed'")
    malas = filas.filter("DataQualityEvaluationResult = 'Failed'")
    filas_ok, filas_cuarentena = ok.count(), malas.count()

    reglas = resultados_de_reglas(dq)
    frescura = evaluar(dyf_limpio, REGLA_FRESCURA, "silver_ventas_frescura")
    reglas += [{**r, "critica": False} for r in resultados_de_reglas(frescura)]

    control = control_calidad(filas_leidas, filas_ok, filas_cuarentena, reglas)
    print(f"Control de calidad: {json.dumps(control, ensure_ascii=False)}")

    # 4. Cuarentena. Se conserva aunque la fuente esté rota: ahí se ve qué ha llegado
    if filas_cuarentena:
        # Se guardan los valores originales de bronze, no los transformados. El event_id nulo
        # es justo uno de los motivos de rechazo: de ahí la comparación que admite nulos
        originales = con_columnas(bronze, COLUMNAS_BRONZE).dropDuplicates(["event_id"])
        claves = malas.select(F.col("event_id").alias("id_rechazado"), "DataQualityRulesFail")
        unidas = originales.join(claves, originales["event_id"].eqNullSafe(claves["id_rechazado"]))
        a_cuarentena(unidas).writeTo("glue_catalog.silver.ventas_cuarentena").append()

    escribir_control(control)
    if fuente_rota(control):
        raise RuntimeError(f"Fuente rota: {control['pct_cuarentena']} % de las filas en cuarentena")

    # 5. MERGE en silver: un evento ya cargado no se vuelve a insertar
    nuevas = ok.select(*COLUMNAS_SILVER_VENTAS).withColumn("fecha_carga", F.current_timestamp())
    nuevas.createOrReplaceTempView("nuevas")
    spark.sql("""
        MERGE INTO glue_catalog.silver.ventas t
        USING nuevas s
          ON t.event_id = s.event_id
        WHEN NOT MATCHED THEN INSERT *
    """)

    job.commit()  # guarda el bookmark


main()
