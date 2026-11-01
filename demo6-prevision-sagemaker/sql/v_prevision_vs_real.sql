-- Real frente a previsto. Sin schema binding, porque el despliegue de la demo 4 borra y recrea
-- mv_ventas_diarias, y una vista normal lo impediría.
CREATE OR REPLACE VIEW gold.v_prevision_vs_real AS
WITH reales AS (
  SELECT fecha_sk, pais, familia, SUM(unidades) AS unidades_reales
  FROM gold.mv_ventas_diarias
  GROUP BY 1, 2, 3
), previstas AS (
  SELECT fecha_sk, pais, familia, unidades_previstas
  FROM gold.fct_prevision
  WHERE fecha_calculo = (SELECT MAX(fecha_calculo) FROM gold.fct_prevision)
)
SELECT d.fecha,
       COALESCE(r.fecha_sk, p.fecha_sk) AS fecha_sk,
       COALESCE(r.pais, p.pais)         AS pais,
       COALESCE(r.familia, p.familia)   AS familia,
       r.unidades_reales,
       p.unidades_previstas
FROM reales r
FULL JOIN previstas p ON p.fecha_sk = r.fecha_sk AND p.pais = r.pais AND p.familia = r.familia
JOIN gold.dim_fecha d ON d.fecha_sk = COALESCE(r.fecha_sk, p.fecha_sk)
WITH NO SCHEMA BINDING;

GRANT SELECT ON gold.v_prevision_vs_real TO ROLE lector_gold_completo;
