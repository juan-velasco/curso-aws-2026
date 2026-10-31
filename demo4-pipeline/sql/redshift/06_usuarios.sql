-- ${password_quicksight_ro} y ${rol_pipeline} los sustituye desplegar_redshift.py.
-- Si el usuario ya existe, el script sigue adelante.
CREATE USER quicksight_ro PASSWORD '${password_quicksight_ro}';
ALTER USER quicksight_ro PASSWORD '${password_quicksight_ro}';
GRANT USAGE ON SCHEMA gold TO quicksight_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO quicksight_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO quicksight_ro;

-- La máquina de estados entra por la Data API con su rol de IAM
CREATE USER "IAMR:${rol_pipeline}" PASSWORD DISABLE;
GRANT USAGE ON SCHEMA gold TO "IAMR:${rol_pipeline}";
GRANT EXECUTE ON PROCEDURE gold.sp_cargar_gold(TIMESTAMP, TIMESTAMP) TO "IAMR:${rol_pipeline}";
