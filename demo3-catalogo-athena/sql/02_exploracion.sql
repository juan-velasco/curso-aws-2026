-- Exploración de bronze. athena.py sustituye la fecha con --fecha AAAA-MM-DD;
-- en la consola, pon los valores a mano (por ejemplo, '2026', '10' y '24').

-- ¿Cuántos eventos y cuántos duplicados hay ese día?
SELECT count(*)                 AS eventos,
       count(DISTINCT event_id) AS unicos
FROM bronze.ventas
WHERE anio = '${fecha_anio}' AND mes = '${fecha_mes}' AND dia = '${fecha_dia}';

-- Top 5 productos por venta neta del día
SELECT producto_id,
       sum(unidades * precio_unitario
           - descuento)         AS venta_neta
FROM bronze.ventas
WHERE anio = '${fecha_anio}' AND mes = '${fecha_mes}' AND dia = '${fecha_dia}'
GROUP BY producto_id
ORDER BY venta_neta DESC
LIMIT 5;
