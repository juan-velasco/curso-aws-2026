# Estado del repositorio al cerrar la sesión 2

Punto de partida para preparar el handoff de la sesión 3. Recoge el estado **real** del repositorio y de la cuenta de pruebas el 30-10-2026, comprobado con Terraform, AWS CLI y boto3. Complementa a `ESTADO_SESION1.md`, que sigue vigente para bronze y las demos 1 y 2.

Donde aparece `<ID de cuenta>`, el valor real se obtiene con `terraform -chdir=infra/base output -raw account_id`.

---

## 1. Qué falta

| Pieza | Estado |
|---|---|
| Demo 3 | **Completa** y probada contra AWS |
| Demo 4: silver, gold y orquestación | **Completa** y probada contra AWS |
| QuickSight (`quicksight.tf`, guion) | Fuente de datos, dataset e importación **probados**, y refresco desde la máquina de estados. **Análisis y dashboard sin hacer**: son a mano. Los nombres de menús del guion están sin comprobar |
| Lake Formation (`infra-lakeformation/`) | **Aplicado y sigue activo.** Criterios de permisos probados asumiendo los roles por API, pipeline en verde con el módulo aplicado y ciclo `destroy` + `apply` comprobado: ajustes del lago idénticos, sin ubicaciones, LF-Tags, filtros ni permisos. Puede quedar un opt-in residual de un rol borrado (2 de 3 ciclos), y `apply` puede dar un timeout transitorio: ver el guion |
| Rol `analista_asia` y RLS en Redshift | **Desplegados, pero sin comprobar** con un usuario de ese rol. Sí está comprobado que `quicksight_ro` ve todas las filas con RLS activo |

## 2. Árbol añadido

```
├── CAMBIOS_DIAPOSITIVAS.md
├── ESTADO_SESION2.md
├── HANDOFF_SESION2.md
├── comun/
│   ├── athena.py, redshift.py       # ejecutar SQL desde los scripts
│   ├── eventos.py                   # extraído del generador: FabricaVentas y patrones del histórico
│   ├── referencia.py                # tipos de cambio y calendario
│   └── tests/
├── demo1-ingesta/scripts/
│   ├── backfill_ventas.py
│   └── tests/
├── demo3-catalogo-athena/
│   ├── GUION.md
│   ├── infra/                       # main.tf: bases de datos, crawler, workgroup
│   ├── sql/                         # 01_bronze_ventas, 02_exploracion, 03_iceberg_prueba, 04_bronze_clientes
│   └── scripts/                     # athena.py, comprobar_demo3.py
└── demo4-pipeline/
    ├── GUION.md, GUION_LAKE_FORMATION.md
    ├── infra/                       # glue, red, redshift, stepfunctions, quicksight
    ├── infra-lakeformation/
    ├── glue/                        # 2 jobs, transformaciones.py, tests/
    ├── sql/athena/silver.sql
    ├── sql/redshift/                # 01 a 07
    ├── stepfunctions/               # pipeline.asl.json, tests/
    └── scripts/                     # crear_silver, cargar_referencia, desplegar_redshift, cargar_gold_inicial,
                                     # ejecutar_pipeline, comprobar_demo4, tests/
```

## 3. Terraform

| Módulo | Estado | Lee de |
|---|---|---|
| `infra/base`, `demo1-ingesta/infra` | Desplegados, sin cambios | Ver `ESTADO_SESION1.md` |
| `demo2-cdc-dms/infra` | Destruido. Ahora declara el log group `dms-tasks-curso-aws-hp-demo2` (7 días); el residual se borró | `infra/base` |
| `demo3-catalogo-athena/infra` | Desplegado (7 recursos) | `infra/base` |
| `demo4-pipeline/infra` | Desplegado (35 recursos, con QuickSight) | `infra/base` |
| `demo4-pipeline/infra-lakeformation` | Desplegado (20 recursos). Aplicar y destruir con `-parallelism=1` | `infra/base` |

Etiquetas: `sesion = 2` y `demo = demo3 | demo4 | lakeformation`. Región `eu-west-1`. En la cuenta de pruebas, `perfil = "default"` en los `terraform.tfvars`, que no están en git.

**Outputs.**

| Módulo | Outputs |
|---|---|
| demo3 | `bucket_name`, `region`, `workgroup` (`curso`), `crawler` (`curso-bronze-cdc`), `base_datos_bronze`, `base_datos_silver` |
| demo4 | `bucket_name`, `region`, `jobs_glue`, `redshift_workgroup` (`hp-retail`), `redshift_endpoint`, `secreto_admin_arn`, `secreto_quicksight_ro`, `rol_pipeline`, `maquina_arn`, `tema_sns`, `quicksight_dataset_id`, `quicksight_dataset_arn` |

**Variables de demo4:** `perfil`, `email_alertas` (obligatoria), `clase_ejecucion_glue` (`STANDARD`), `cidr_vpc` (`10.30.0.0/16`), `cidr_quicksight` (`52.210.255.224/27`), `mi_ip` (detectada), `rpu_base` (4), `programacion_activa` (`false`), `quicksight_activo` (`false`), `quicksight_usuario_arn`.

## 4. Rutas en S3

| Uso | Ruta |
|---|---|
| Histórico | `bronze/ventas/anio=AAAA/mes=MM/dia=DD/backfill-AAAA-MM-DD-NNN.json.gz` |
| Silver | `silver/<tabla>/` (Iceberg) |
| Control de calidad | `control/calidad/ventas/ultima.json` |
| Scripts de los jobs | `artefactos/glue/` |
| Resultados de Athena | `athena-results/` (caducan a los 7 días) |

## 5. Esquema real

**Catálogo `bronze`:** `ventas` (DDL con partition projection), `clientes` (DDL, sin particiones, con `op`), `productos` (crawler).

**Catálogo `silver`:** las 7 tablas de `sql/athena/silver.sql`, Iceberg en formato Parquet: `ventas` y `ventas_cuarentena` (particionadas por día), `dim_cliente`, `dim_producto`, `tiendas`, `tipos_cambio` y `calendario`.

**`gold` en Redshift (`dev`):** `dim_cliente`, `dim_producto`, `dim_tienda`, `dim_fecha`, `fct_ventas`, la auxiliar `tienda_pais`, `mv_ventas_diarias`, `v_dashboard_ventas` y los procedimientos `sp_cargar_dimensiones` y `sp_cargar_gold(TIMESTAMP, TIMESTAMP)`.

**Para la sesión 3 (previsión).** `gold.mv_ventas_diarias` tiene `fecha_sk`, `pais`, `familia`, `color`, `talla`, `unidades` y `venta_neta` (EUR). Fuera de la ventana de ayer y hoy, la máquina de estados no recarga: si silver cambia hacia atrás, hay que lanzar `cargar_gold_inicial.py`.

## 6. Volumen

| Dato | Valor |
|---|---|
| Backfill | 120 días, del 02-07-2026 al 29-10-2026: 260.462 eventos, 185 ficheros, 2 % de duplicados |
| Firehose | 1.803 (sesión 1) + 6.305 (10 min pico, 5 % duplicados) + 1.269 + 1.269 + 1.268 (2 min de prueba) |
| `silver.ventas` | 266.780 filas, sin duplicados. `ventas_cuarentena`: 0 filas |
| `silver.dim_cliente` / `dim_producto` | 4.002 / 1.200 filas |
| `gold.fct_ventas` | 266.780 filas |
| Dataset SPICE `ventas_dashboard` | 266.780 filas, 0 descartadas |
| `gold.mv_ventas_diarias` | ~101.750 filas |

**La cuarentena no se ha probado con datos reales.** Todos los eventos pasan por la API, que ya los valida, así que siempre ha estado vacía. Tampoco se ha ejercitado la rama `pct_cuarentena > 5` en AWS ni el umbral del 50 %, salvo en tests locales de `control_calidad`.

## 7. Qué sigue desplegado

**Desplegado:** además de lo de la sesión 1, bases de datos, crawler y workgroup de Athena; 2 jobs de Glue; VPC y red; namespace y workgroup de Redshift, con su límite; SNS con suscripción confirmada; máquina de estados y Scheduler **desactivado**; roles y secretos.

**Lake Formation sigue activo:** `silver/` registrado en modo híbrido, LF-Tags, filtro `analistas_asia` y los roles `curso-analista-asia`, `curso-data-science` y `curso-lakeformation-acceso`. Los ajustes de la cuenta (administradores y permisos por defecto) no han cambiado: `get-data-lake-settings` coincide con la copia previa.

**Con coste aunque no se use:**
- **Amazon Quick:** activada el 30-10-2026, edición Enterprise, usuario `ADMIN_PRO`. Según la página de precios, la prueba dura 30 días y **después se factura solo: 250 USD/mes de infraestructura por cuenta más 40 USD/mes por usuario**. Hay que cancelarla antes del 29-11-2026 (`quicksight_activo = false` y aplicar antes de cancelar). No está confirmado que esta cuenta esté en prueba: la API no lo muestra
- **IP elástica del workgroup público:** ~3,60 USD/mes. Contradice «nada con coste por hora salvo Redshift mientras consulta», y el handoff la pasó por alto.
- **Dos secretos:** ~0,80 USD/mes.

Con eso, el presupuesto de 10 USD/mes queda bien, pero conviene decírselo a los alumnos.

## 8. Roles IAM nuevos

| Rol | Para qué |
|---|---|
| `curso-bronze-cdc-crawler` | Crawler. `AWSGlueServiceRole` + lectura de `bronze/cdc/*` |
| `curso-aws-hp-glue-jobs` | Jobs. Lee `bronze/ventas`, `bronze/cdc` y `artefactos`; lee y escribe `silver` y `control`; catálogo sobre `silver`; logs, métricas y Data Quality |
| `curso-aws-hp-redshift` | Rol por defecto del namespace. Catálogo y S3 de `silver`, solo lectura |
| `curso-aws-hp-pipeline` | Máquina de estados. Jobs, control, Data API (`DescribeStatement` sobre `*`, sin alternativa), `GetCredentials`, SNS |
| `curso-aws-hp-pipeline-scheduler` | Scheduler. `states:StartExecution` |

Usuarios de Redshift: `admin_retail` (secreto gestionado por Redshift), `quicksight_ro`, `"IAMR:curso-aws-hp-pipeline"`. Roles: `analista_asia`, `lector_gold_completo` (lleva `IGNORE RLS`).

## 9. Desviaciones respecto a HANDOFF_SESION2.md

Las que afectan a las diapositivas están en `CAMBIOS_DIAPOSITIVAS.md`. Además:

| Tema | Handoff | Real | Motivo |
|---|---|---|---|
| Crawler | Crea `clientes` y `productos` | Solo `productos`; `clientes` con DDL | Ver `CAMBIOS_DIAPOSITIVAS.md` |
| Lake Formation | `data_lake_settings` conservando administradores | No se declara. Se exige que quien aplica sea administrador | Su `destroy` vacía la configuración de la cuenta, según recuerdo del proveedor, sin comprobar. El usuario ya es administrador |
| `comun/` | `eventos.py`, `referencia.py` | También `athena.py` y `redshift.py` | Los usan las demos 3 y 4 |
| Volumen del backfill | ~180.000 | 260.462 | Los factores multiplican el volumen |
| Subredes | «Suelen ser 3» | 3, aunque bastan 2 | Margen ante una AZ sin servicio |
| Capacidad | «Comprueba si es 4 u 8» | 4 RPU | Admitida en `eu-west-1` |
| Compactación de `silver.ventas` | Opcional | Fuera | No hacía falta para la demo |
| `sp_cargar_gold` desde `cargar_gold_inicial.py` | Ventana del histórico | Del primer día de silver a mañana, y `REFRESH` de la vista | La vista también se refresca sola, pero así queda al día al terminar |

**Pasos de los guiones.** Los seis pasos de las demos 3 y 4 siguen el texto de las diapositivas, facilitado por el profesor. En la demo 3, el Iceberg de prueba queda como extra opcional, porque no es uno de los seis pasos.

| `venta_rebajas` en QuickSight | `ifelse(es_rebajas, venta_neta, 0)` | `ifelse({es_rebajas} = 1, {venta_neta}, 0.0)` con `es_rebajas` como `BIT` | `SYNTAX_ERROR` con la original |
| `terraform apply` de Lake Formation | Sin indicar | `-parallelism=1` | Los opt-in en paralelo fallan con `ConcurrentModificationException` |

## 10. Versiones y tests

| Componente | Versión |
|---|---|
| Glue | 5.0 (Spark 3.5.4, Python 3.11), `G.1X`, 2 workers |
| `pyspark` en desarrollo | 3.5.4, con `setuptools` 84.2.1. Necesita Java 8, 11 o 17; probado con 11 y Python 3.12 |
| Redshift Serverless | 4 RPU de base, máximo 16, 10 RPU-hora al día |
| Proveedores de Terraform | Los de la sesión 1 |

```bash
pip install -r requirements-dev.txt
pytest                          # 76 tests, ~15 s, sin AWS
ruff check .
terraform fmt -check -recursive
```

Contra AWS:

```bash
python demo3-catalogo-athena/scripts/comprobar_demo3.py --fecha 2026-10-28
python demo4-pipeline/scripts/comprobar_demo4.py
```

**Ejecuciones reales de la máquina:** correcta (2 min 20 s, de `SilverEnParalelo` a `NotificarOK`), sin datos (`SinDatos`, ~2 min), fallo forzado (`Fallido` tras 3 intentos, 6 min, gold intacto).
