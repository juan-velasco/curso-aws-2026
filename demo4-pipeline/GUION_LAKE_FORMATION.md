# Guion · Lake Formation (solo el profesor)

**Solo en una cuenta de pruebas. Los alumnos no lo activan en sus cuentas de empresa.**

**Duración:** ~10 min. Va después de las diapositivas de Lake Formation y antes del ejercicio C.

> **Probado en la cuenta de pruebas** el 30-10-2026: los criterios de los pasos 5 y 6, y el pipeline completo con el módulo aplicado. También el ciclo `destroy` y `apply`: los ajustes del lago quedan idénticos a la copia previa, sin ubicaciones, LF-Tags ni filtros. **Puede quedar un opt-in residual** de un rol ya borrado: pasó en 2 de 3 ciclos y es inofensivo (ver [Después de la clase](#después-de-la-clase)). **Falta comprobar la vista de la consola**, porque las pruebas se hicieron asumiendo los roles por API.

## Qué toca en la cuenta

- **Modo de acceso híbrido:** se registra solo `s3://<bucket>/silver/`. Los permisos de Lake Formation solo se aplican a los dos roles con *opt-in*. Los jobs de Glue, Redshift y el resto de usuarios siguen con IAM.
- **La configuración del lago no se modifica.** El módulo no declara `aws_lakeformation_data_lake_settings`, porque ese recurso sustituye la configuración de toda la cuenta y su `destroy` deja vacíos los administradores y los permisos por defecto. Solo exige que quien aplica ya sea administrador del lago, y falla en el `plan` si no lo es. Para serlo, añádete en **Lake Formation → Administrative roles and tasks**, conservando a los que ya estén.

## Antes de la clase

1. Guarda la configuración actual:
   ```bash
   aws lakeformation get-data-lake-settings --profile curso --region eu-west-1 > lf-antes.json
   ```
2. Aplica el módulo:
   ```bash
   cd demo4-pipeline/infra-lakeformation
   terraform init && terraform plan     # revisa el plan: no debe aparecer data_lake_settings
   terraform apply -parallelism=1       # los opt-in en paralelo fallan con ConcurrentModificationException
   terraform output url_switch_role
   cd ../..
   ```
3. Comprueba los criterios de los pasos 5 y 6 con los dos roles.

## En clase

1. **Recuerda la advertencia** de la diapositiva «Lake Formation en una cuenta de empresa».
2. **Consola de Lake Formation:** administradores del lago, ubicación `silver/` registrada en modo híbrido y los dos roles con *opt-in*.
3. **LF-Tags:** `capa` y `sensibilidad`, y las columnas `nombre`, `email` y `telefono` de `silver.dim_cliente` marcadas como `pii`.
4. **Filtro de datos `analistas_asia`:** filas `pais IN ('JP', 'CN')` y columnas sin `cliente_id`. Relaciónalo con el JSON de la diapositiva «Filtro de filas y columnas».
5. **Cambia al rol `curso-analista-asia`** (*switch role*), abre Athena en el workgroup `curso` y consulta:
   ```sql
   SELECT pais, count(*) FROM silver.ventas GROUP BY pais;   -- solo JP y CN (en las pruebas, 51.888 y 45.320)
   SELECT * FROM silver.ventas LIMIT 5;                      -- no aparece cliente_id
   ```
6. **Cambia al rol `curso-data-science`** y consulta `SELECT * FROM silver.dim_cliente LIMIT 5`: no aparecen `nombre`, `email` ni `telefono`. Como `curso-analista-asia`, esa misma tabla ni siquiera existe (`TABLE_NOT_FOUND`).
7. **Vuelve al rol del profesor:** la misma consulta ve todo. El modo híbrido solo restringe a los principales con *opt-in*; los jobs de Glue y Redshift siguen funcionando con IAM.
8. **Enlaza con el ejercicio C** (matriz de permisos).

## Después de la clase

```bash
cd demo4-pipeline/infra-lakeformation
terraform destroy -parallelism=1
cd ../..
aws lakeformation get-data-lake-settings --profile curso --region eu-west-1 > lf-despues.json
```

Compara `lf-antes.json` y `lf-despues.json`: deben coincidir.

Comprueba que no quede ningún opt-in. En 2 de 3 ciclos de prueba quedó uno de un rol ya borrado:

```bash
aws lakeformation list-lake-formation-opt-ins --profile curso --region eu-west-1
```

Si aparece, bórralo con `aws lakeformation delete-lake-formation-opt-in`, indicando su `Principal` y su `Resource`. En un `apply` posterior, el rol se recrea con el mismo ARN y el opt-in vuelve a quedar bajo Terraform.

## Si algo falla

- **`Quien aplica debe ser administrador del lago`:** añádete como administrador en la consola, conservando los que ya haya, y repite.
- **`Insufficient Lake Formation permission(s)` con un rol de la demo:** falta el *opt-in* de ese rol sobre esa tabla, o el permiso. Revisa **Lake Formation → Data permissions** y **Hybrid access mode**.
- **`ConcurrentModificationException` o `Invalid principal` al crear un opt-in:** son los opt-in en paralelo. Repite con `terraform apply -parallelism=1`.
- **`reading Lake Formation permissions: timeout` en `analista_filtro`:** es consistencia eventual justo después de crear el filtro. El permiso sí se ha creado: repite el `apply`.
- **`PERMISSION_DENIED ... s3:GetObject` con un rol de la demo:** el opt-in aún no existe. Termina el `apply`.
- **El rol ve todas las filas:** el *opt-in* no se ha aplicado. En modo híbrido, un principal sin *opt-in* sigue con IAM.
