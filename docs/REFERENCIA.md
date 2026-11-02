# Referencia técnica

Nombres, rutas, esquemas y decisiones del repositorio. Lo que hay desplegado hoy está en [ESTADO.md](ESTADO.md).

Donde aparece `<ID de cuenta>`, el valor se obtiene con `terraform -chdir=infra/base output -raw account_id`.

## Terraform

Cada módulo tiene su **estado local**, sin backend remoto. Los módulos leen a los anteriores con `terraform_remote_state`, y los scripts con `comun/terraform.py`. La región se define solo en `infra/base`.

| Módulo | Recursos | Lee de | Coste si está desplegado |
|---|---|---|---|
| `infra/base` | 6 | | Céntimos |
| `demo1-ingesta/infra` | 9 con email, 7 sin él | base | Por GB |
| `demo2-cdc-dms/infra` | 31 | base | **~0,06 USD/h** |
| `demo3-catalogo-athena/infra` | 7 | base | Céntimos |
| `demo4-pipeline/infra` | 36 con QuickSight | base | Ver [estado](ESTADO.md#qué-hay-desplegado) |
| `demo4-pipeline/infra-lakeformation` | 20. Aplicar y destruir con `-parallelism=1` | base | |
| `demo5-api-fargate/infra` | 13 | base, demo 1 | Sin tareas, nada |
| `demo6-prevision-sagemaker/infra` | 12, y 13 con QuickSight | base, demo 4 | Sin space, nada |
| `ejercicio-f-cognito/infra` | 12 | base | Nivel gratuito |
| `ejercicio-g-guardduty-inspector/infra` | 8 | base | Prueba gratuita |

Los outputs y variables de cada módulo están en sus `outputs.tf` y `variables.tf`.

**El security group de la demo 2, la demo 4 y la demo 5 admite una IP concreta,** detectada al aplicar. Al cambiar de red, hay que aplicar de nuevo.

Etiquetas: `proyecto = curso-aws-hp`, `sesion = 1 | 2 | 3` y `demo = <módulo>`.

## Rutas en S3

Bucket `retail-company-datalake-prod-<ID de cuenta>`: acceso público bloqueado, SSE-S3, versionado y `force_destroy = true`.

| Uso | Ruta |
|---|---|
| Ventas de Firehose | `bronze/ventas/anio=AAAA/mes=MM/dia=DD/hp-retail-ventas-1-….json.gz` |
| Histórico | `bronze/ventas/anio=AAAA/mes=MM/dia=DD/backfill-AAAA-MM-DD-NNN.json.gz` |
| Errores de Firehose | `errors/ventas/<tipo de error>/AAAA/MM/DD/` |
| CDC, carga completa | `bronze/cdc/public/<tabla>/LOAD00000001.parquet` |
| CDC, cambios | `bronze/cdc/public/<tabla>/AAAA/MM/DD/AAAAMMDD-HHMMSSmmm.parquet` |
| Silver | `silver/<tabla>/` (Iceberg) |
| Control de calidad | `control/calidad/ventas/ultima.json` |
| Scripts de los jobs | `artefactos/glue/` |
| Resultados de Athena | `athena-results/` (caducan a los 7 días) |
| Serie y calendario | `ml/ventas_diarias/`, `ml/calendario/` (UNLOAD con `CLEANPATH`) |
| Clima inventado | `ml/clima/clima.parquet` |
| Previsión | `ml/predicciones/fecha_calculo=AAAA-MM-DD/prevision.csv` |
| Ruta opcional | `ml/train/`, `ml/valid/`, `ml/entrada_bt/`, `ml/checkpoints/`, `ml/modelos/`, `ml/codigo/`, `ml/predicciones_bt/` |

**Lifecycle.** `bronze/`: Standard-IA a 30 días, Glacier IR a 90 y Deep Archive a 365. Versiones no actuales: expiran a 30 días. Subidas multiparte incompletas: se abortan a 7.

## Datos

### Maestros

`comun/maestros.py` es la **única fuente** de tiendas, clientes y productos, y es determinista: cada tabla tiene su semilla. Los usan el generador, el backfill y la carga de RDS.

- **Tiendas:** 21 físicas y 5 online (`ONL-ES`, `ONL-FR`, `ONL-US`, `ONL-JP`, `ONL-CN`). ES 6 y FR 4 en EUR, US 4 en USD, JP 4 en JPY, CN 3 en CNY. Regiones: Europa, América y Asia.
- **Clientes:** 4.000, de `C-1` a `C-4000`. Standard ~80 %, Premium ~20 %.
- **Productos:** 1.200 = 100 modelos × 3 colores × 4 tallas. `producto_id`: `P-<modelo>-<color>-<talla>`.
- **Casos fijos:** C-17 pasa de Standard a Premium en la demo 2. C-981 se borra. C-4001 se inserta (Standard, Lyon, FR). `P-0412-ROJ-M` es un vestido de 39,95 EUR.
- **Tipos de cambio fijos e ilustrativos:** 1 EUR = 1,08 USD = 160 JPY = 7,8 CNY.

### Bronze: ventas

JSON Lines con gzip real, extensión `.json.gz` y `Content-Encoding: gzip`. Por eso, al descargarlos desde la consola, el navegador los guarda ya descomprimidos. Athena y Glue leen los bytes tal cual.

| Campo | Tipo | Notas |
|---|---|---|
| `event_id` | string | UUID v4 |
| `event_ts` | string | UTC con milisegundos y `Z` |
| `canal` | string | `TPV`, `WEB` o `APP` |
| `tienda_id` | string | `ES-VLC-003`, `ONL-ES` |
| `ticket_id` | string | `T-<AAAAMMDD>-<nº de tienda>-<secuencia>`, con `000` online. **La clave es `(tienda_id, ticket_id)`:** el número de tienda solo es único dentro de un país |
| `linea` | integer | 1–4 |
| `cliente_id` | string o null | Nulo en ~30 % de los tickets |
| `producto_id` | string | |
| `unidades` | integer | 1, 2 o 3 |
| `precio_unitario` | number | En moneda local |
| `descuento` | number | **Importe total de la línea**, no unitario |
| `moneda` | string | `EUR`, `USD`, `JPY`, `CNY` |
| `medio_pago` | string | |

**Las particiones son la fecha de llegada a Firehose, en UTC,** no `event_ts`. En el histórico, la del evento.

### Bronze: CDC de DMS

Parquet. Columnas de datos de `clientes` y `productos`, más:

- **`Op`:** solo en los ficheros de cambios, como primera columna: `I`, `U`, `D`. **No existe en la carga completa.**
- **`ts_commit`:** es **string** (`2026-10-28 17:23:34.470161`, UTC), no timestamp.
- **`precio_catalogo` y `coste_unitario`:** `decimal(8,2)`.
- **Filas `D`:** llegan completas, por `REPLICA IDENTITY FULL`.

### Catálogo y Redshift

| Capa | Tablas | Definición |
|---|---|---|
| `bronze` | `ventas` (DDL con partition projection), `clientes` (DDL, sin particiones), `productos` (crawler) | `demo3-catalogo-athena/sql/` |
| `silver` | `ventas` y `ventas_cuarentena` (por día), `dim_cliente`, `dim_producto`, `tiendas`, `tipos_cambio`, `calendario`. Iceberg en Parquet, importes en EUR | `demo4-pipeline/sql/athena/silver.sql` |
| `gold` (Redshift, base de datos `dev`) | `dim_cliente`, `dim_producto`, `dim_tienda`, `dim_fecha`, `fct_ventas`, `tienda_pais`, `mv_ventas_diarias`, `v_dashboard_ventas`, procedimientos `sp_cargar_dimensiones` y `sp_cargar_gold(TIMESTAMP, TIMESTAMP)` | `demo4-pipeline/sql/redshift/` |
| `gold`, previsión | `fct_prevision`, `v_prevision_vs_real` | `demo6-prevision-sagemaker/sql/` |

**La máquina de estados solo recarga gold de ayer y hoy.** Si silver cambia hacia atrás, lanza `cargar_gold_inicial.py`.

### Volumen de la cuenta de pruebas (01-11-2026)

| Dato | Valor |
|---|---|
| Histórico | 120 días, del 02-07 al 29-10-2026: 260.462 eventos, 185 ficheros, 2 % de duplicados |
| `silver.ventas`, `gold.fct_ventas` | 268.580 filas. En bronze, 274.176 líneas |
| `silver.dim_cliente` / `dim_producto` | 4.002 / 1.200 |
| `gold.mv_ventas_diarias` | 102.592 |
| `gold.fct_prevision` | 1.120 filas, fecha de cálculo 2026-11-01 |
| Datasets SPICE | `ventas_dashboard` y `prevision_vs_real` (6.000 filas) |

Gold termina el 01-11-2026, con atípicos por los generadores de prueba: 11.035 unidades el 30-10 y 0 el 31-10.

### Resultados del modelo

| Modelo | WAPE, validación del 05-10 al 01-11 | Sin los 3 últimos días |
|---|---|---|
| Línea base | **0,349** | **0,197** |
| XGBoost sin clima | 0,374 | |
| XGBoost con clima | 0,381 | 0,227 |
| Training job (XGBoost 1.7-1, con clima) | 0,3766 | |

Con 120 días no se ha visto octubre al entrenar, y la feature con más ganancia es `mes`. Calendario > clima se cumple.

## Roles IAM

| Rol o política | Para qué |
|---|---|
| `firehose-hp-retail-ventas` | Firehose escribe en `bronze/ventas/*`, `errors/ventas/*` y sus logs |
| `api-ventas-firehose-put` (política) | Solo `PutRecord` y `PutRecordBatch` sobre el stream. La usa el task role, y el alumno si le faltan permisos |
| `dms-vpc-role`, `dms-cloudwatch-logs-role` | De cuenta, con nombre fijo. Si ya existen: `crear_roles_dms = false` |
| `curso-aws-hp-dms-secreto`, `curso-aws-hp-dms-s3` | DMS lee su secreto y escribe en `bronze/cdc/*` |
| `curso-bronze-cdc-crawler` | Crawler, con lectura de `bronze/cdc/*` |
| `curso-aws-hp-glue-jobs` | Lee `bronze/ventas`, `bronze/cdc` y `artefactos`; lee y escribe `silver` y `control` |
| `curso-aws-hp-redshift` | Por defecto del namespace. Lee `silver`; lee y escribe `ml/*` |
| `curso-aws-hp-pipeline`, `curso-aws-hp-pipeline-scheduler` | Máquina de estados y Scheduler |
| `curso-analista-asia`, `curso-data-science`, `curso-lakeformation-acceso` | Lake Formation |
| `curso-aws-hp-ecs-ejecucion` | ECS descarga la imagen y escribe logs |
| `api-ventas-task` | La API. Solo `api-ventas-firehose-put`, con `aws:SourceAccount` en la confianza |
| `curso-aws-hp-sagemaker` | Studio y sus jobs. `AmazonSageMakerFullAccess` y, del lago, solo `ml/` |

**Usuarios de Redshift:** `admin_retail` (secreto gestionado por Redshift), `quicksight_ro`, `"IAMR:curso-aws-hp-pipeline"`. **Roles:** `analista_asia`, `lector_gold_completo` (con `IGNORE RLS`). Una tabla o vista nueva necesita `GRANT SELECT` para `lector_gold_completo`.

## Decisiones de diseño

Lo que difiere de las diapositivas está en [CAMBIOS_DIAPOSITIVAS.md](CAMBIOS_DIAPOSITIVAS.md).

| Tema | Decisión | Motivo |
|---|---|---|
| Cliente HTTP | `httpx2` | Lo pide el `TestClient` de la versión actual de Starlette |
| Errores de AWS en la API | 503 también ante `ClientError` o `BotoCoreError` | Con un 500, el generador no reintenta y el error no se ve |
| `event_ts` | `field_serializer` en `Venta` | Si no, Pydantic escribe microsegundos |
| DMS | `dms.t3.small`, motor 3.6.1, PostgreSQL 17 | AWS ya no ofrece `dms.t3.micro` |
| DMS: captura | `REPLICA IDENTITY FULL`, `capture_ddls = false` | `D` con la fila completa; `dms_user` no es superusuario |
| Glue lee `bronze/ventas` de S3 | Con bookmarks, sin el catálogo | Partition projection solo funciona en Athena |
| Lake Formation | Sin `data_lake_settings`; exige que quien aplica ya sea administrador | Ese recurso sustituye la configuración de toda la cuenta |
| Modo híbrido | Solo `silver/`, con opt-in de los roles de la demo | Glue y Redshift siguen con IAM |
| Capacidad de Redshift | 4 RPU de base, 16 de máximo, tope de 10 RPU-hora al día | La mínima en `eu-west-1` |
| QuickSight sin VPC | Workgroup público; 5439 solo desde el rango de QuickSight y tu IP | La opción más simple. Cuesta la IP elástica |
| `v_prevision_vs_real` | `WITH NO SCHEMA BINDING` | `05_vistas.sql` recrea `mv_ventas_diarias`. **Sin probar:** relanzar `desplegar_redshift.py` con esta vista creada |
| `preparar_datos.py` | Refresca la vista, crea `fct_prevision` y `v_prevision_vs_real`, y lanza el UNLOAD | Sin refresco falta el último día |
| Clima | Inventado, tras `preparar_datos.py` | Cubre hasta 28 días tras el último día de gold |
| Previsión | Reentrenada con todo el histórico y `best_iteration + 1` | Si no, ignora los últimos 28 días |
| SDK de SageMaker | `sagemaker==2.257.7`, en un entorno aparte | La versión 3 retiró los estimadores, y sus dependencias no deben mezclarse |
| Métrica del training job | `metricas.json`, dentro de `model.tar.gz` | El contenedor rechaza `metric_definitions` |
| Batch transform | Crea un modelo temporal desde la versión aprobada y lo borra | No deja modelos sueltos |
| Apagado de JupyterLab | 60 min, con mínimo de 60 y máximo de 480 | La API exige mínimo y máximo |
| User pool | `ESSENTIALS`, explícito | Es el plan por defecto, el de la consola de los alumnos |
| `estado_servicios.py` | `--guardar` y `--comparar`; compara solo los tipos activos | Criterio de `destroy`. La API añade tipos nuevos, como `ami` |

**Limitación conocida del SCD2:** la granularidad es de día. Las ventas de C-17 del 28-10-2026 anteriores a las 17:23 quedan asociadas a la versión Premium.

## Versiones y tests

| Componente | Versión |
|---|---|
| Terraform | `>= 1.6`. Proveedor `hashicorp/aws` `~> 6.70` |
| Python | 3.12; imágenes `python:3.12-slim` |
| Dependencias | Fijadas en `requirements.txt`, `requirements-dev.txt`, `requirements-opcional.txt` y los de `api/` y `generador/` |
| Glue | 5.0 (Spark 3.5.4, Python 3.11), `G.1X`, 2 workers |
| `pyspark` en desarrollo | 3.5.4. Necesita Java 8, 11 o 17 |
| SageMaker Distribution | Python 3.12, xgboost 2.1.4, pandas 2.3.3, sin SDK `sagemaker` |
| Contenedor de entrenamiento | `sagemaker-xgboost:1.7-1` |

```bash
pip install -r requirements-dev.txt
pytest                          # 130 tests, sin AWS
ruff check .
terraform fmt -check -recursive
```

Contra AWS, con la terminal [preparada](../README.md#preparar-la-terminal):

```bash
python demo1-ingesta/scripts/comprobar_bronze.py --fecha AAAA-MM-DD
python demo2-cdc-dms/scripts/comprobar_cdc.py                       # con la demo 2 desplegada
python demo3-catalogo-athena/scripts/comprobar_demo3.py --fecha 2026-10-28
python demo4-pipeline/scripts/comprobar_demo4.py
python demo5-api-fargate/scripts/comprobar_demo5.py --parado
python demo6-prevision-sagemaker/scripts/comprobar_demo6.py
python ejercicio-f-cognito/scripts/probar_api.py
python ejercicio-g-guardduty-inspector/scripts/estado_servicios.py
```
