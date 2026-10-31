-- Iceberg desde Athena sobre una tabla de prueba: particionado oculto, time travel y
-- mantenimiento. La tabla se borra al final. ${bucket} lo sustituye athena.py.

-- Crear una tabla Iceberg con particionado oculto
CREATE TABLE silver.ventas_prueba (
  event_id string, fecha_venta timestamp,
  tienda_id string, importe decimal(12,2))
PARTITIONED BY (day(fecha_venta))
LOCATION 's3://${bucket}/silver/prueba/'
TBLPROPERTIES ('table_type' = 'ICEBERG');

-- Dos escrituras: dos snapshots
INSERT INTO silver.ventas_prueba VALUES
  ('e1', TIMESTAMP '2026-10-24 10:15:32', 'ES-VLC-001', DECIMAL '39.95'),
  ('e2', TIMESTAMP '2026-10-25 11:20:00', 'FR-PAR-001', DECIMAL '59.95');

INSERT INTO silver.ventas_prueba VALUES
  ('e3', TIMESTAMP '2026-10-25 12:45:10', 'JP-TYO-001', DECIMAL '19.95');

SELECT count(*) AS filas_ahora FROM silver.ventas_prueba;

-- Time travel: la tabla hace 5 segundos (en la diapositiva, una hora: esta tabla es recién creada)
SELECT count(*) AS filas_hace_5_s FROM silver.ventas_prueba
FOR TIMESTAMP AS OF (current_timestamp - interval '5' second);

-- Mantenimiento
OPTIMIZE silver.ventas_prueba REWRITE DATA USING BIN_PACK;
VACUUM silver.ventas_prueba;

-- Limpieza
DROP TABLE silver.ventas_prueba;
