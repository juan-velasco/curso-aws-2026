-- Serie diaria y calendario a S3 en Parquet.
-- CLEANPATH borra lo anterior: se puede repetir sin que queden ficheros de otra ejecución.
UNLOAD ('SELECT fecha_sk, pais, familia,
                SUM(unidades) AS unidades
         FROM gold.mv_ventas_diarias GROUP BY 1, 2, 3')
TO 's3://${bucket}/ml/ventas_diarias/'
IAM_ROLE default FORMAT AS PARQUET CLEANPATH;

UNLOAD ('SELECT * FROM gold.dim_fecha')
TO 's3://${bucket}/ml/calendario/'
IAM_ROLE default FORMAT AS PARQUET CLEANPATH;
