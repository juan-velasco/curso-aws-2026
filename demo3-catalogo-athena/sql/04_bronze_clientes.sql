-- bronze.clientes no la puede crear el crawler. DMS deja la carga completa en la raíz de la
-- tabla, sin Op, y los cambios en AAAA/MM/DD/, con Op. El crawler avisa con "Found schemas
-- don't match ... Can not create Tables" y crea una tabla por fichero. Una tabla sin particiones
-- sí lo resuelve: Athena recorre las subcarpetas y lee Parquet por nombre de columna, así
-- que op es NULL en la carga completa e I, U o D en los cambios. ${bucket} lo sustituye athena.py.
CREATE EXTERNAL TABLE IF NOT EXISTS bronze.clientes (
  op string, ts_commit string, cliente_id string, nombre string, email string,
  telefono string, segmento string, provincia string, pais string,
  fecha_alta date, actualizado_en timestamp)
STORED AS PARQUET
LOCATION 's3://${bucket}/bronze/cdc/public/clientes/';
