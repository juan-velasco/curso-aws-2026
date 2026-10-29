-- Usuario de DMS con permisos mínimos: replicación lógica y lectura de public.
-- No se usa el usuario maestro. cargar_semilla.py sustituye el marcador de la contraseña
-- con el valor del secreto de Secrets Manager.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dms_user') THEN
        CREATE ROLE dms_user LOGIN;
    END IF;
END
$$;

ALTER ROLE dms_user WITH LOGIN PASSWORD {password};

GRANT rds_replication TO dms_user;
GRANT USAGE ON SCHEMA public TO dms_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO dms_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO dms_user;
