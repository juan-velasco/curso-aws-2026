-- Tabla de bronze con partition projection: Athena calcula las particiones a partir
-- de la consulta, sin crawler ni MSCK REPAIR. Solo funciona en Athena: Glue y Redshift
-- Spectrum no la usan. ${bucket} lo sustituye athena.py; en la consola, ponlo a mano.
-- ${anio}, ${mes} y ${dia} los resuelve Athena: no se tocan.
CREATE EXTERNAL TABLE IF NOT EXISTS bronze.ventas (
  event_id string, event_ts string, canal string, tienda_id string,
  ticket_id string, linea int, cliente_id string, producto_id string,
  unidades int, precio_unitario double, descuento double,
  moneda string, medio_pago string)
PARTITIONED BY (anio string, mes string, dia string)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://${bucket}/bronze/ventas/'
TBLPROPERTIES (
  'projection.enabled'     = 'true',
  'projection.anio.type'   = 'integer', 'projection.anio.range' = '2024,2030',
  'projection.mes.type'    = 'integer', 'projection.mes.range'  = '1,12',
  'projection.mes.digits'  = '2',
  'projection.dia.type'    = 'integer', 'projection.dia.range'  = '1,31',
  'projection.dia.digits'  = '2',
  'storage.location.template' =
    's3://${bucket}/bronze/ventas/anio=${anio}/mes=${mes}/dia=${dia}/'
);
