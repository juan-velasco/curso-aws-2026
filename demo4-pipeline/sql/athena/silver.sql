-- Tablas Iceberg de silver (formato v2). Las crea crear_silver.py con Athena.
-- ${bucket} lo sustituye el script.

CREATE TABLE IF NOT EXISTS silver.ventas (
  event_id string, fecha_venta timestamp, canal string, tienda_id string,
  ticket_id string, linea int, cliente_id string, producto_id string,
  unidades int, precio_unitario decimal(12,2), moneda string,
  importe_bruto decimal(12,2), descuento decimal(12,2),
  medio_pago string, pais string, fecha_carga timestamp)
PARTITIONED BY (day(fecha_venta))
LOCATION 's3://${bucket}/silver/ventas/'
TBLPROPERTIES ('table_type' = 'ICEBERG', 'format' = 'parquet');

CREATE TABLE IF NOT EXISTS silver.ventas_cuarentena (
  event_id string, event_ts string, canal string, tienda_id string,
  ticket_id string, linea string, cliente_id string, producto_id string,
  unidades string, precio_unitario string, descuento string,
  moneda string, medio_pago string, motivo string, fecha_carga timestamp)
PARTITIONED BY (day(fecha_carga))
LOCATION 's3://${bucket}/silver/ventas_cuarentena/'
TBLPROPERTIES ('table_type' = 'ICEBERG', 'format' = 'parquet');

CREATE TABLE IF NOT EXISTS silver.dim_cliente (
  cliente_id string, nombre string, email string, telefono string,
  segmento string, provincia string, pais string, fecha_alta date,
  valid_from date, valid_to date, is_current boolean, es_baja boolean,
  ts_ultimo_cambio timestamp)
LOCATION 's3://${bucket}/silver/dim_cliente/'
TBLPROPERTIES ('table_type' = 'ICEBERG', 'format' = 'parquet');

CREATE TABLE IF NOT EXISTS silver.dim_producto (
  producto_id string, modelo string, color string, talla string,
  familia string, temporada string,
  precio_catalogo decimal(8,2), coste_unitario decimal(8,2),
  valid_from date, valid_to date, is_current boolean, es_baja boolean,
  ts_ultimo_cambio timestamp)
LOCATION 's3://${bucket}/silver/dim_producto/'
TBLPROPERTIES ('table_type' = 'ICEBERG', 'format' = 'parquet');

CREATE TABLE IF NOT EXISTS silver.tiendas (
  tienda_id string, nombre string, pais string, region string, ciudad string,
  formato string, superficie_m2 int, es_online boolean, moneda string)
LOCATION 's3://${bucket}/silver/tiendas/'
TBLPROPERTIES ('table_type' = 'ICEBERG', 'format' = 'parquet');

CREATE TABLE IF NOT EXISTS silver.tipos_cambio (
  moneda string, eur_por_unidad decimal(18,8))
LOCATION 's3://${bucket}/silver/tipos_cambio/'
TBLPROPERTIES ('table_type' = 'ICEBERG', 'format' = 'parquet');

CREATE TABLE IF NOT EXISTS silver.calendario (
  fecha_sk int, fecha date, anio int, mes int, nombre_mes string,
  semana_iso int, dia_semana int, nombre_dia string, es_fin_de_semana boolean,
  temporada string, es_rebajas boolean, es_festivo boolean)
LOCATION 's3://${bucket}/silver/calendario/'
TBLPROPERTIES ('table_type' = 'ICEBERG', 'format' = 'parquet');
