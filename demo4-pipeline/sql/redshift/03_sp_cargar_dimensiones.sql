-- Dimensiones desde silver. Las versiones se identifican por id + valid_from: un cambio en
-- silver actualiza la vigencia y una versión nueva recibe su propia clave subrogada.
CREATE OR REPLACE PROCEDURE gold.sp_cargar_dimensiones()
AS $$
BEGIN
  DROP TABLE IF EXISTS stg_cliente;
  CREATE TEMP TABLE stg_cliente AS
  SELECT cliente_id, segmento, provincia, pais, valid_from, valid_to, is_current
  FROM silver.dim_cliente;

  MERGE INTO gold.dim_cliente USING stg_cliente s
    ON  gold.dim_cliente.cliente_id = s.cliente_id
    AND gold.dim_cliente.valid_from = s.valid_from
  WHEN MATCHED THEN UPDATE SET
    segmento = s.segmento, provincia = s.provincia, pais = s.pais,
    valid_to = s.valid_to, is_current = s.is_current
  WHEN NOT MATCHED THEN INSERT
    (cliente_id, segmento, provincia, pais, valid_from, valid_to, is_current)
    VALUES (s.cliente_id, s.segmento, s.provincia, s.pais,
            s.valid_from, s.valid_to, s.is_current);

  DROP TABLE IF EXISTS stg_producto;
  CREATE TEMP TABLE stg_producto AS
  SELECT producto_id, modelo, color, talla, familia, temporada, valid_from, valid_to, is_current
  FROM silver.dim_producto;

  MERGE INTO gold.dim_producto USING stg_producto s
    ON  gold.dim_producto.producto_id = s.producto_id
    AND gold.dim_producto.valid_from  = s.valid_from
  WHEN MATCHED THEN UPDATE SET
    modelo = s.modelo, color = s.color, talla = s.talla,
    familia = s.familia, temporada = s.temporada,
    valid_to = s.valid_to, is_current = s.is_current
  WHEN NOT MATCHED THEN INSERT
    (producto_id, modelo, color, talla, familia, temporada, valid_from, valid_to, is_current)
    VALUES (s.producto_id, s.modelo, s.color, s.talla, s.familia, s.temporada,
            s.valid_from, s.valid_to, s.is_current);

  -- Tiendas: SCD1
  DROP TABLE IF EXISTS stg_tienda;
  CREATE TEMP TABLE stg_tienda AS
  SELECT tienda_id, nombre, pais, region, ciudad, formato, superficie_m2
  FROM silver.tiendas;

  MERGE INTO gold.dim_tienda USING stg_tienda s
    ON gold.dim_tienda.tienda_id = s.tienda_id
  WHEN MATCHED THEN UPDATE SET
    nombre = s.nombre, pais = s.pais, region = s.region, ciudad = s.ciudad,
    formato = s.formato, superficie_m2 = s.superficie_m2
  WHEN NOT MATCHED THEN INSERT
    (tienda_id, nombre, pais, region, ciudad, formato, superficie_m2)
    VALUES (s.tienda_id, s.nombre, s.pais, s.region, s.ciudad, s.formato, s.superficie_m2);

  DELETE FROM gold.tienda_pais;
  INSERT INTO gold.tienda_pais SELECT tienda_sk, pais FROM gold.dim_tienda;

  -- Calendario: se recarga entero, no tiene historia
  DELETE FROM gold.dim_fecha;
  INSERT INTO gold.dim_fecha
  SELECT fecha_sk, fecha, anio, mes, nombre_mes, semana_iso, dia_semana, nombre_dia,
         es_fin_de_semana, temporada, es_rebajas, es_festivo
  FROM silver.calendario;
END;
$$ LANGUAGE plpgsql;
