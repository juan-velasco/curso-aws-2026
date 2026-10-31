-- Vista materializada para la previsión de la sesión 3. Usa tienda_pais: no admite dim_tienda, con RLS
DROP MATERIALIZED VIEW IF EXISTS gold.mv_ventas_diarias;

CREATE MATERIALIZED VIEW gold.mv_ventas_diarias
AUTO REFRESH YES AS
SELECT f.fecha_sk, t.pais, p.familia, p.color, p.talla,
       SUM(f.unidades)                     AS unidades,
       SUM(f.importe_bruto - f.descuento)  AS venta_neta
FROM gold.fct_ventas f
JOIN gold.tienda_pais t  ON t.tienda_sk   = f.tienda_sk
JOIN gold.dim_producto p ON p.producto_sk = f.producto_sk
GROUP BY 1, 2, 3, 4, 5;

-- Una fila por línea de venta, para QuickSight
CREATE OR REPLACE VIEW gold.v_dashboard_ventas AS
SELECT d.fecha, f.fecha_sk, d.anio, d.semana_iso, d.mes, d.es_rebajas,
       t.pais, t.region, t.tienda_id,
       p.familia, p.color, p.talla,
       c.segmento,
       t.tienda_id || '-' || f.ticket_id   AS clave_ticket,
       f.unidades,
       f.importe_bruto - f.descuento       AS venta_neta
FROM gold.fct_ventas f
JOIN gold.dim_fecha d    ON d.fecha_sk    = f.fecha_sk
JOIN gold.dim_tienda t   ON t.tienda_sk   = f.tienda_sk
JOIN gold.dim_producto p ON p.producto_sk = f.producto_sk
JOIN gold.dim_cliente c  ON c.cliente_sk  = f.cliente_sk;
