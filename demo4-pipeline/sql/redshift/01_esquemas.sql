-- Silver visible en Redshift sin moverlo
CREATE EXTERNAL SCHEMA IF NOT EXISTS silver
FROM DATA CATALOG
DATABASE 'silver'
IAM_ROLE default;

-- Esquema de la capa gold
CREATE SCHEMA IF NOT EXISTS gold;
