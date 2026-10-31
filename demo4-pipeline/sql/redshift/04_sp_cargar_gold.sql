-- Carga de la ventana [p_desde, p_hasta): borra e inserta, así que repetirla no duplica.
-- SECURITY DEFINER: quien la ejecuta solo necesita EXECUTE, no permisos sobre las tablas.
CREATE OR REPLACE PROCEDURE gold.sp_cargar_gold(
    p_desde TIMESTAMP, p_hasta TIMESTAMP)
AS $$
BEGIN
  CALL gold.sp_cargar_dimensiones();

  DELETE FROM gold.fct_ventas
   WHERE fecha_sk >= TO_CHAR(p_desde, 'YYYYMMDD')::INT
     AND fecha_sk <  TO_CHAR(p_hasta, 'YYYYMMDD')::INT;

  INSERT INTO gold.fct_ventas
  SELECT TO_CHAR(v.fecha_venta, 'YYYYMMDD')::INT AS fecha_sk,
         COALESCE(c.cliente_sk, -1)          AS cliente_sk,
         p.producto_sk,
         t.tienda_sk,
         v.ticket_id, v.linea, v.unidades,
         v.importe_bruto, v.descuento
  FROM silver.ventas v
  LEFT JOIN gold.dim_cliente c
    ON  c.cliente_id = v.cliente_id
    AND v.fecha_venta >= c.valid_from
    AND v.fecha_venta <  c.valid_to
  JOIN gold.dim_producto p
    ON  p.producto_id = v.producto_id
    AND v.fecha_venta >= p.valid_from
    AND v.fecha_venta <  p.valid_to
  JOIN gold.dim_tienda t
    ON  t.tienda_id = v.tienda_id
  WHERE v.fecha_venta >= p_desde AND v.fecha_venta < p_hasta;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
