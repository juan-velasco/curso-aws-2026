# Cambios propuestos a las diapositivas

Diferencias entre las diapositivas y lo que funciona al probarlo contra AWS. Las citas son del anexo A de `HANDOFF_SESION2.md` y de `HANDOFF_SESION3.md`.

## Sesión 1

Los cambios de esta sesión ya se aplicaron a las diapositivas y el fichero se borró entonces.

## Sesión 2

### Desviaciones previstas en el handoff

| Diapositiva | Texto actual | Texto propuesto | Motivo |
|---|---|---|---|
| 56 · Silver en paralelo | `"Parameters": { "JobName": "bronze-a-silver-ventas" }` | Añadir `"Arguments": { "--FORZAR_FALLO.$": "$.opciones.forzar_fallo" }` | Permite provocar el fallo del paso 6 desde la entrada de la ejecución |
| 56 · Silver en paralelo | `"Next": "CalidadOK"` | `"Next": "LeerCalidad"` | El resultado de Data Quality está en S3: un estado `LeerCalidad` lo lee con `aws-sdk:s3:getObject` y `States.StringToJson` antes de decidir |
| 26 · SCD2 con MERGE | Siempre cierra la vigente y abre una versión | Si la vigente se abrió ese mismo día, se actualiza | Evita versiones de duración cero |
| Glue Data Quality | Umbral sin concretar | Más del 50 % en cuarentena: el job falla (fuente rota). Más del 5 %: `CalidadOK` va a `NotificarFallo` | Distingue una fuente rota de un lote con errores |

### Encontrado al probar

| Diapositiva | Texto actual | Texto propuesto | Motivo |
|---|---|---|---|
| 24 · Ventas | `.withColumn("pais", F.substring("tienda_id", 1, 2))` | `F.when(F.col("tienda_id").startswith("ONL-"), F.substring("tienda_id", 5, 2)).otherwise(F.substring("tienda_id", 1, 2))` | **Error:** en las tiendas online (`ONL-ES`) devuelve `ON` como país |
| 24 · Ventas | `.join(F.broadcast(cambio), "moneda")` | `.join(F.broadcast(cambio), "moneda", "left")` | **Error:** con INNER JOIN, una moneda desconocida desaparece en silencio y la regla de `moneda` de Data Quality nunca la ve |
| 24 · Ventas | `.filter("unidades >= 1 AND producto_id IS NOT NULL")` | Quitar el filtro | Si se filtra antes, Data Quality no ve esas filas y nunca llegan a cuarentena |
| 29 · Data Quality | `DataFreshness "fecha_venta" <= 24 hours` en las mismas reglas | Evaluarla aparte, sin separar filas | **Error:** a nivel de fila mandaría todo el histórico a cuarentena. Con el histórico, solo el 2,64 % de las filas la cumple. Se añade también `IsComplete "fecha_venta"` |
| 21 · Anatomía de un Glue Job | No muestra cómo terminar | Avisar: para terminar antes de tiempo, usar `return` | `sys.exit(0)` hace que Glue marque el job como `FAILED` con `SystemExit: 0` |
| 26 · SCD2 con MERGE | MERGE + INSERT sobre un lote | Versiones calculadas en orden y un único MERGE por clave + `valid_from` | Es más claro para aplicar la carga completa y los cambios en orden de `ts_commit`, y es idempotente. Se calcula en el driver: son miles de filas |
| 57 · Cargar gold | `"Id.$": "$.Id"`, `"Variable": "$.Status"` | `"ResultPath": "$.gold"`, `"Id.$": "$.gold.Id"`, `"Variable": "$.estado_gold.Status"` | Sin `ResultPath`, cada estado sobrescribe la entrada y se pierde el control de calidad que necesita `NotificarOK` |
| 57 · Cargar gold | `CALL gold.sp_cargar_gold(current_date-1, current_date+1)` | `CALL gold.sp_cargar_gold((current_date-1)::TIMESTAMP, (current_date+1)::TIMESTAMP)` | Los parámetros son `TIMESTAMP`: conversión explícita. La forma sin conversión no se ha probado |
| 57 · Cargar gold | Solo `FINISHED` y `FAILED` | Añadir `ABORTED` a la rama de fallo | Una sentencia cancelada dejaría el bucle en marcha para siempre |
| 56 y siguientes | Empieza en `SilverEnParalelo` | Estado inicial `Preparar` | `forzar_fallo` es opcional: una ejecución sin entrada usa `false` |
| 40 y 47 · Gold | `mv_ventas_diarias` con `JOIN gold.dim_tienda`, y RLS sobre `gold.dim_tienda` | `mv_ventas_diarias` con `JOIN gold.tienda_pais`, tabla auxiliar con `tienda_sk` y `pais` | **Error:** son incompatibles: `Materialized view base table "dim_tienda" is not supported` |
| 47 · Permisos del motor | Termina en `ROW LEVEL SECURITY ON` | Añadir `GRANT IGNORE RLS TO ROLE lector_gold_completo` y `GRANT ROLE lector_gold_completo TO quicksight_ro` | Con RLS activo, quien no tiene política no ve filas: el dashboard quedaría vacío. `IGNORE RLS` no se puede conceder a un usuario, solo a un rol |
| 38 · dim_cliente | Sin `pais` | Con `pais` | El handoff lo incluye como atributo SCD2 |
| Crawlers | El crawler crea `clientes` y `productos` sobre `bronze/cdc/public/` | El crawler rastrea solo `productos`; `bronze.clientes` se crea con DDL (`sql/04_bronze_clientes.sql`) | Con la carga en la raíz, sin `Op`, y los cambios en `AAAA/MM/DD/`, con `Op`, crea tablas `load00000001_parquet` y `2026` y avisa `Found schemas don't match ... Can not create Tables`. Probado con exclusiones y con varios niveles de tabla. Athena sí lee la mezcla en una tabla sin particiones |
| Crawlers | Exclusiones de la diapositiva | Comprobar | No tenía el texto de la diapositiva: usé `**/_SUCCESS`, `**/*.tmp` y `**/_temporary/**` |
| 16 · Athena e Iceberg | `FOR TIMESTAMP AS OF (current_timestamp - interval '1' hour)` y `silver.ventas` | Sin cambios en la diapositiva. El fichero usa `interval '5' second` y `silver.ventas_prueba` | La tabla de prueba es recién creada y falla si se le pide una hora |
| 15 · Explorar bronze | «Top 5 productos por venta neta» | Añadir una nota | Suma importes de monedas distintas, así que dominan los de JPY. Sirve como ejemplo de por qué hace falta silver |
| Conectar QuickSight con gold | `venta_rebajas = ifelse(es_rebajas, venta_neta, 0)` | `ifelse({es_rebajas} = 1, {venta_neta}, 0.0)`, con `es_rebajas` como columna `BIT` en el dataset | **Error:** QuickSight responde `SYNTAX_ERROR`: un booleano no vale como condición. Se comprobó la expresión al crear el dataset; `es_rebajas` queda como `INTEGER` (0 o 1) |
| Suscripción de QuickSight | «QuickSight» | «Amazon Quick (antes QuickSight)» | La consola ya usa el nombre nuevo. La API sigue siendo `quicksight` |
| Suscripción de QuickSight | «No activar usuarios Pro» | Comprobar, y añadir: «al acabar los 30 días se factura sola: 250 USD/mes por cuenta más 40 USD/mes por usuario» | Al activar la cuenta de pruebas, el administrador aparece como `ADMIN_PRO`. Lo que cuesta es importante para alumnos con cuenta de empresa |
| Coste de Redshift | «Sin consultas no hay cómputo» | Añadir: «pero un workgroup público tiene una IP elástica, ~3,60 USD/mes» | El endpoint público lleva una IPv4 que se cobra aunque no haya consultas |

### Comprobado: sin cambios

| Tema | Resultado |
|---|---|
| Athena y `.json.gz` con `Content-Encoding: gzip` | Lee bien: 3.395 líneas en Athena y en S3 el 28-10 |
| Glue, bookmarks y `.json.gz` | Lee y descomprime bien; la segunda ejecución lee 0 filas |
| Redshift Serverless en `eu-west-1` | Admite 4 RPU de base. Sin Enhanced VPC Routing bastan 2 subredes en 2 AZ; se usan 3 |
| Rango de IP de QuickSight en `eu-west-1` | `52.210.255.224/27` |

### Notas (no son cambios)

- **Granularidad de día del SCD2.** Las ventas del 28-10-2026 anteriores al cambio de C-17 (17:23) quedan asociadas a la versión Premium, porque `valid_from` es una fecha. Limitación conocida.
- **Nivel de tabla de los crawlers.** Para `TableLevelConfiguration`, la API cuenta el bucket como nivel 1: `bucket/bronze/cdc/public/productos` es el nivel 5, aunque la documentación diga que la carpeta superior es el 1.
- **Volumen del backfill.** Son ~260.000 eventos, no ~180.000: los factores de fin de semana y rebajas multiplican el volumen, y los 120 días incluyen julio y agosto.

## Sesión 3

Las diapositivas de seguridad (65 en adelante) **aún no las ha revisado el profesor**.

### Desviaciones previstas en el handoff

| Diapositiva | Texto actual | Texto propuesto | Motivo |
|---|---|---|---|
| 10 · Task definition | `environment` solo con `FIREHOSE_STREAM` | Añadir `{ "name": "AWS_REGION", "value": "eu-west-1" }` | **Error:** la API no arranca sin ella |
| 10 · Task definition | `executionRoleArn` con `ecsTaskExecutionRole` | Rol propio `curso-aws-hp-ecs-ejecucion` | En una cuenta de empresa, `ecsTaskExecutionRole` puede existir y ser compartido |
| 15 · Comandos | `docker buildx build ... .` sin indicar desde dónde | Avisar: se lanza desde `demo1-ingesta/api/` | Es el contexto de build |
| 15 · Comandos | `aws ecr create-repository --repository-name api-ventas` | Añadir `--image-scanning-configuration scanOnPush=true` | Se ve el escaneo básico, y enlaza con el ejercicio G |

### Encontrado al probar

| Diapositiva | Texto actual | Texto propuesto | Motivo |
|---|---|---|---|
| 15 · Comandos | `create-service` justo después de `create-cluster` | Añadir una nota: «La primera vez que la cuenta usa ECS, puede fallar: espera 30 s y repite» | Falló con `Unable to assume the service linked role`: AWS acababa de crear `AWSServiceRoleForECS`. A los 20 s funcionó |
| 49 · UNLOAD | `IAM_ROLE default FORMAT AS PARQUET` | Añadir `CLEANPATH` | Sin ninguna de las dos opciones, el handoff indica que el segundo UNLOAD falla (no se ha probado). `CLEANPATH` probado: se lanzó dos veces. Se prefiere a `ALLOWOVERWRITE`, que puede dejar partes antiguas si cambia el número de ficheros |
| 49 · UNLOAD | Lee `gold.mv_ventas_diarias` directamente | Lanzar antes `REFRESH MATERIALIZED VIEW gold.mv_ventas_diarias` | Con `AUTO REFRESH`, tras terminar el pipeline la vista seguía sin el último día, y el clima salía 2 días corto |
| 55 · Entrenar | Termina al evaluar | Añadir: reentrenar con todo el histórico, y las iteraciones de `best_iteration`, antes de prever | Si no, la previsión no aprende de los últimos 28 días. Ver sección 8 del notebook |
| 56 · Training job | `sagemaker.get_execution_role()` y `from sagemaker.xgboost.estimator import XGBoost` | Avisar: instalar `sagemaker<3` (probado con 2.257.7) | La versión 3 retiró los estimadores, y la imagen de Studio no trae el SDK |
| 56 · Training job | Sin rutas de salida | Añadir `output_path`, `code_location` y `sagemaker.Session(default_bucket=bucket)` | Si no, el SDK crea un bucket `sagemaker-<región>-<cuenta>` |
| 56 · Training job | `framework_version="1.7-1"`, sin más | Añadir una nota: «Studio trae XGBoost 2.1.4: el notebook y el training job usan versiones distintas» | El contenedor `1.7-1` sigue disponible en `eu-west-1` y admite `enable_categorical`. En esa versión, el callback se escribe `TrainingCheckPoint`: `TrainingCheckpoint` falla con `AttributeError` |
| 56 · Training job | Sin métricas | Avisar: el contenedor rechaza `metric_definitions` | `You can't override the metric definitions for Amazon SageMaker algorithms`. El WAPE se guarda en `metricas.json`, dentro de `model.tar.gz` |
| 62 · Qué comprobar | «El modelo gana a la línea base» | «Compara el modelo con la línea base. Con 120 días, puede no ganar» | **No gana:** WAPE 0,349 de la línea base frente a 0,374 sin clima y 0,381 con clima. Sin los 3 últimos días, atípicos, 0,197 frente a 0,227. No se ha forzado |
| 76 · Solución del ejercicio G | «Decenas de hallazgos `[SAMPLE]`» | Comprobar en la consola | En la API, `Title` no lleva `[SAMPLE]`: la marca es `"sample": true` en `Service.AdditionalInfo.Value`. La consola no se ha mirado, ni se ha medido el número con todos los tipos |
| 76 · Solución del ejercicio G | Imagen slim «con muy pocos y ninguno crítico» | Sin cambios, con cifras: 24 frente a 8.401, y 0 críticos frente a 431 | Coincide. Paquete con más CVE en `python:3.8`: `linux`, 7.679 |
| 76 · Nota del orador | «Puede tardar unos minutos» | «Puede tardar más de 20 minutos» | La imagen de `python:3.8` (364 MB) seguía en `PENDING` a los 20 min, y estaba `ACTIVE` antes de los 25 |
| 76 · Qué se pide | «¿Llegó el email?» | Añadir: «Mira en el correo no deseado» | En la prueba no se vio a la primera, aunque SNS lo había entregado |

### Comprobado: sin cambios

| Tema | Resultado |
|---|---|
| 10 y 11 · Fargate y task role | `cpu 256`, `memory 512`, ARM64. La API escribe en Firehose sin claves, con el rol y la política de la diapositiva |
| 55 · Modelo en Studio | `XGBRegressor` con los hiperparámetros de la diapositiva, en `ml.t3.medium`: menos de 1 s. La imagen ya trae `xgboost`, `pandas` y `s3fs` |
| 55 · Importancia de features | Calendario > clima. Ganancia: `mes` 60,4, `temp_media` 0,7 y `lluvia_mm` 0,6 |
| 67 a 69 · Cognito | 401 sin token, 200 con el ID token sin `Bearer`, y `cognito:groups` en el token |
| 72 · Regla de EventBridge | El patrón funciona: el correo llega para un hallazgo de ejemplo de severidad 8,0 |

### Notas (no son cambios)

- **Último día de gold.** Tras la demo 5, gold termina el 01-11-2026 (2.082 unidades), con el 31-10 a 0 y el 30-10 a 11.035 por los generadores de prueba. Los alumnos con otros datos verán otros WAPE.
- **RLS en la demo 4 (diapositiva 47).** Comprobado con un usuario temporal con el rol `analista_asia`: al unir con `dim_tienda`, solo ve JP y CN. **Pero `SELECT count(*) FROM gold.fct_ventas`, sin unir, devuelve las 268.580 filas**, porque la política está en `dim_tienda`. Y `gold.dim_cliente` no tiene columna `email`: el `GRANT` por columnas no protege nada en esa tabla.
