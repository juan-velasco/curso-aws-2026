-- Permisos del propio motor: un rol de analista que solo ve Asia y no ve datos personales.
-- Si el rol o la política ya existen, el script sigue adelante.
CREATE ROLE analista_asia;
GRANT USAGE ON SCHEMA gold TO ROLE analista_asia;
GRANT SELECT ON gold.fct_ventas, gold.dim_producto,
                gold.dim_fecha, gold.dim_tienda
      TO ROLE analista_asia;
GRANT SELECT (cliente_sk, segmento, provincia)
      ON gold.dim_cliente TO ROLE analista_asia;

CREATE RLS POLICY solo_asia
WITH (pais VARCHAR(2))
USING (pais IN ('JP', 'CN'));

ATTACH RLS POLICY solo_asia
  ON gold.dim_tienda TO ROLE analista_asia;
ALTER TABLE gold.dim_tienda ROW LEVEL SECURITY ON;

-- Con RLS activo, quien no tiene política no ve ninguna fila: sin esto, el dashboard quedaría
-- vacío. IGNORE RLS solo se puede conceder a un rol, no a un usuario.
CREATE ROLE lector_gold_completo;
GRANT IGNORE RLS TO ROLE lector_gold_completo;
GRANT ROLE lector_gold_completo TO quicksight_ro;
