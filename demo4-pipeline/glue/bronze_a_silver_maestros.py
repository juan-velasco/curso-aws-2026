"""Job de Glue: maestros de CDC de bronze a silver con SCD2.

Lee los Parquet nuevos de bronze/cdc/public/clientes/ y productos/ (bookmarks) y
fusiona las versiones resultantes en silver.dim_cliente y silver.dim_producto.
La lógica de versiones está en transformaciones.py.
"""

import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext

from transformaciones import CLIENTES, PRODUCTOS, aplicar_scd2

args = getResolvedOptions(sys.argv, ["JOB_NAME", "BUCKET", "FORZAR_FALLO"])
glue = GlueContext(SparkContext())
spark = glue.spark_session
spark.conf.set("spark.sql.session.timeZone", "UTC")
job = Job(glue)
job.init(args["JOB_NAME"], args)

if args["FORZAR_FALLO"].lower() == "true":
    raise RuntimeError("FORZAR_FALLO = true: fallo provocado para la demo")

for maestro, carpeta in ((CLIENTES, "clientes"), (PRODUCTOS, "productos")):
    dyf = glue.create_dynamic_frame.from_options(
        connection_type="s3",
        format="parquet",
        connection_options={"paths": [f"s3://{args['BUCKET']}/bronze/cdc/public/{carpeta}/"], "recurse": True},
        transformation_ctx=f"bronze_{carpeta}",  # bookmark
    )
    lote = dyf.toDF()
    if not lote.columns or lote.isEmpty():
        print(f"{carpeta}: sin ficheros nuevos")
        continue

    tabla = f"glue_catalog.silver.{maestro.tabla}"
    aplicar_scd2(spark, maestro, spark.table(tabla), lote).createOrReplaceTempView("versiones")
    print(f"{carpeta}: {spark.table('versiones').count()} versiones a fusionar")
    spark.sql(f"""
        MERGE INTO {tabla} t
        USING versiones s
          ON t.{maestro.clave} = s.{maestro.clave} AND t.valid_from = s.valid_from
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)

job.commit()  # guarda el bookmark
