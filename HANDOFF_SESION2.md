# Handoff: código de las demos de la sesión 2 · Curso AWS para HP

> **Para el profesor.** Copia este fichero en la raíz del repositorio como `HANDOFF_SESION2.md`, junto a `ESTADO_SESION1.md`, y pide a Claude Code: *«Lee HANDOFF_SESION2.md y ESTADO_SESION1.md y construye la sesión 2 siguiendo el plan de trabajo. Pregúntame antes de cualquier acción que cree, modifique o borre recursos en AWS»*. Usa la misma cuenta de pruebas de la sesión 1.

---

## 1. Contexto y alcance

Este repositorio ya contiene las demos 1 y 2 de la sesión 1 (ingesta en streaming y CDC con DMS), construidas y probadas contra AWS. `ESTADO_SESION1.md` describe su estado real: es la fuente de verdad sobre nombres, rutas, esquemas y versiones, y **prevalece sobre `HANDOFF.md`** donde haya diferencias.

La **sesión 2** lleva el dato de bronze a gold y lo enseña en un dashboard. Hay que construir:

| Pieza | Qué enseña | Quién la usa |
|---|---|---|
| **Demo 3 · Catálogo y Athena sobre bronze** | Glue Data Catalog, crawler, partition projection, workgroup de Athena, exploración y coste por datos escaneados | Profesor y alumnos |
| **Demo 4 · El pipeline de punta a punta** | Glue Jobs (bronze → silver en Iceberg, SCD2, Data Quality), Redshift Serverless (gold con ELT), Step Functions, SNS, QuickSight | Profesor y alumnos |
| **Lake Formation** | LF-Tags, filtros de filas y columnas, permisos por perfil | **Solo el profesor**, en una cuenta de pruebas |

El código de las diapositivas de la sesión 2 está en el **anexo A**. El repositorio debe respetarlo; donde no sea posible o haya una forma mejor, se anota en `CAMBIOS_DIAPOSITIVAS.md` (§11). Las demos se llaman **3** y **4** porque la numeración es correlativa en todo el curso.

### Restricciones generales (las mismas de la sesión 1)

- **Coste mínimo.** Cada alumno usa su propia cuenta de empresa. Nada con coste por hora encendido salvo Redshift Serverless mientras se consulta (sin consultas no hay cómputo).
- **Multiplataforma.** Scripts en Python, no en bash. Comandos en bash y PowerShell en los guiones si difieren.
- **Idioma.** README, guiones, comentarios y logs en español.
- **Sin secretos en git.** Estados de Terraform, `terraform.tfvars`, `.env` y `salida/` siguen en `.gitignore`.
- **No romper la sesión 1.** `pytest`, `ruff` y `terraform validate` de lo existente deben seguir pasando.

---

## 2. Decisiones ya tomadas

| Tema | Decisión |
|---|---|
| Carpetas nuevas | `demo3-catalogo-athena/` y `demo4-pipeline/`. Lake Formation en `demo4-pipeline/infra-lakeformation/` |
| Etiquetas | `proyecto = curso-aws-hp`, `sesion = 2`, `demo = demo3 \| demo4 \| lakeformation` |
| Estado de Terraform | Local, como en la sesión 1. Los módulos nuevos leen `infra/base` con `terraform_remote_state` |
| Lectura de `bronze/ventas` en Glue | **Directamente de S3** con `create_dynamic_frame.from_options` y bookmarks. Partition projection solo funciona en Athena: Glue y Redshift Spectrum no la usan |
| Partition projection | Solo para consultar `bronze.ventas` desde Athena (demo 3) |
| Maestros de CDC | Crawler sobre `bronze/cdc/public/` para Athena. Los Glue Jobs leen los Parquet de S3 directamente |
| Tablas sin origen | `fct_stock_diario` **fuera de alcance**. `dim_tienda`, `dim_fecha` y los tipos de cambio se cargan en silver desde `comun/maestros.py` y un calendario generado |
| Silver | Tablas **Iceberg** en `s3://<bucket>/silver/`, base de datos `silver` del Glue Data Catalog |
| Gold | Redshift Serverless: namespace y workgroup `hp-retail`, base de datos `dev`, esquema `gold` |
| Conexión de QuickSight con Redshift | **La más simple**: workgroup accesible desde internet, con security group que solo admite el rango de IP de QuickSight en `eu-west-1` y la IP del profesor. Sin conexión VPC |
| QuickSight | Terraform crea **fuente de datos y dataset** (SPICE). Análisis y dashboard **a mano**, con el guion del anexo B |
| Lake Formation | Solo en la cuenta del profesor, en **modo de acceso híbrido** y con *opt-in* solo para los roles de la demo |
| Workgroup de Athena | `curso`, resultados en `athena-results/`, límite de 10 GB por consulta |
| Programación horaria | EventBridge Scheduler creado **desactivado** por defecto |
| Moneda en silver y gold | Importes en **EUR** con `silver.tipos_cambio`; la columna `moneda` conserva la original |

---

## 3. Lo que hay que tener en cuenta de la sesión 1

De `ESTADO_SESION1.md`, lo que más afecta a la sesión 2:

- **Particiones de ventas por fecha de llegada** (UTC), no por `event_ts`.
- **Ficheros de ventas**: `.json.gz` con gzip real y `Content-Encoding: gzip`. La lectura con Athena **aún no se ha probado**: es lo primero que hay que comprobar en la demo 3.
- **Clave de ticket**: `(tienda_id, ticket_id)`; `ticket_id` solo no es único.
- **`descuento`** es el importe total de la línea, no unitario.
- **CDC**:
  - `ts_commit` es **string** (`2026-10-28 17:23:34.470161`, UTC) y hay que convertirlo.
  - `Op` solo existe en los ficheros CDC, como primera columna.
  - Las filas `D` llegan completas (`REPLICA IDENTITY FULL`).
  - `productos` solo tiene carga completa.
  - `precio_catalogo` y `coste_unitario` son `decimal(8,2)`.
- **Volumen actual**: 1.803 ventas de un solo día, sin duplicados. **Hay que generar más** (§5.1).
- **DMS está destruido**; sus ficheros siguen en `bronze/cdc/`. La sesión 2 no necesita DMS.
- **Pendiente de la sesión 1**: el log group `dms-tasks-curso-aws-hp-demo2` queda fuera de Terraform. Decisión: declararlo en `demo2-cdc-dms/infra/dms.tf` como `aws_cloudwatch_log_group` con retención de 7 días, creado antes que la tarea, para que `destroy` lo borre. Borra a mano el que quedó (pregunta antes).

---

## 4. Estructura del repositorio

Se añade, sin mover nada de lo existente:

```
curso_aws_hp/
├── HANDOFF_SESION2.md
├── ESTADO_SESION1.md
├── CAMBIOS_DIAPOSITIVAS.md          # se vuelve a crear; esta vez no se borra
├── comun/
│   ├── maestros.py                  # + region de la tienda (ver §5.2)
│   ├── eventos.py                   # NUEVO: construcción de eventos compartida (generador y backfill)
│   └── referencia.py                # NUEVO: tipos de cambio y calendario
├── demo1-ingesta/
│   └── scripts/
│       └── backfill_ventas.py       # NUEVO: histórico de ventas directo a bronze
├── demo3-catalogo-athena/
│   ├── GUION.md
│   ├── infra/                       # bases de datos, crawler, workgroup
│   ├── sql/                         # DDL de bronze.ventas, consultas de exploración, Iceberg de prueba
│   └── scripts/                     # athena.py (ejecutar SQL), comprobar_demo3.py
└── demo4-pipeline/
    ├── GUION.md                     # incluye el guion de QuickSight (anexo B)
    ├── GUION_LAKE_FORMATION.md      # anexo C
    ├── infra/                       # Glue, Redshift, red, SNS, Step Functions, Scheduler, QuickSight
    ├── infra-lakeformation/         # solo el profesor
    ├── glue/
    │   ├── bronze_a_silver_ventas.py
    │   ├── bronze_a_silver_maestros.py
    │   ├── transformaciones.py      # funciones puras de PySpark (testeables en local)
    │   └── tests/
    ├── sql/
    │   ├── athena/                  # DDL de las tablas Iceberg de silver
    │   └── redshift/                # esquemas, tablas gold, procedimientos, vistas, usuarios y permisos
    ├── stepfunctions/
    │   └── pipeline.asl.json        # plantilla (templatefile de Terraform)
    └── scripts/
        ├── crear_silver.py          # DDL de silver con Athena
        ├── cargar_referencia.py     # tiendas, tipos de cambio y calendario en silver
        ├── desplegar_redshift.py    # ejecuta sql/redshift con la Data API
        ├── ejecutar_pipeline.py     # lanza la máquina de estados y sigue su estado
        ├── cargar_gold_inicial.py   # CALL sp_cargar_gold con la ventana del histórico
        └── comprobar_demo4.py
```

**Refactor permitido en `comun/`.** Extraer de `demo1-ingesta/generador/generador.py` la construcción de tickets y eventos a `comun/eventos.py`, con una función que reciba la marca de tiempo, para que el backfill genere eventos idénticos en forma a los del generador. El comportamiento del generador no cambia y sus tests deben seguir pasando.

---

## 5. Datos de la sesión 2

### 5.1 Histórico de ventas (`demo1-ingesta/scripts/backfill_ventas.py`)

El dashboard (semanas por país, % en rebajas) y la sesión 3 (previsión con SageMaker) necesitan histórico. El backfill escribe **directamente en S3**, sin pasar por la API ni Firehose, así que no tiene coste de ingesta.

- **Parámetros:** `--dias 120` (por defecto: cubre las rebajas de verano), `--eventos-dia 1500`, `--duplicados-pct 2`, `--hasta` (por defecto, ayer en UTC) y `--forzar`.
- **Ruta y nombre:** `bronze/ventas/anio=AAAA/mes=MM/dia=DD/backfill-AAAA-MM-DD-NNN.json.gz`. Mismo formato que Firehose: JSON Lines comprimido con gzip, un evento por línea, `event_ts` con milisegundos y `Z`. La fecha de la carpeta es la del evento (simula que llegó ese día).
- **Idempotente:** si ya hay ficheros `backfill-` en un día, lo salta salvo con `--forzar`. Nunca toca los ficheros de Firehose.
- **Patrones** (para que el dashboard y la previsión de la sesión 3 tengan señal), multiplicando el volumen diario:
  - fin de semana ×1,3;
  - rebajas ×1,6 (mismas fechas que el calendario, §5.3);
  - estacionalidad por familia: abrigos y punto suben en los meses de OI y baño en los de PV.

  Deja estos factores en constantes documentadas en `comun/eventos.py` o en el propio script.
- **Clientes:** los 4.000 de la semilla. C-4001 no aparece antes del 28-10-2026.
- **Volumen orientativo:** ~180.000 eventos y unos pocos MB.

En la demo 4, además, el generador se lanza con `MODO=pico DUPLICADOS_PCT=5` durante 10 minutos para tener datos del día y duplicados que desduplicar.

### 5.2 Tiendas con región

Añade a `Tienda` en `comun/maestros.py` la propiedad `region`: `Europa` (ES, FR), `América` (US) y `Asia` (JP, CN). No cambies la semilla ni los datos existentes: el test de determinismo debe seguir pasando.

### 5.3 Referencia (`comun/referencia.py`)

- **Tipos de cambio:** tabla `moneda`, `eur_por_unidad` derivada de los de `maestros.py`:
  - EUR 1;
  - USD 1/1,08;
  - JPY 1/160;
  - CNY 1/7,8.

  Precisión de 8 decimales.
- **Calendario** de 2024-01-01 a 2027-12-31, una fila por día:

| Campo | Regla |
|---|---|
| `fecha_sk` | Entero `AAAAMMDD` |
| `fecha`, `anio`, `mes`, `nombre_mes`, `semana_iso`, `dia_semana` (1 = lunes), `nombre_dia` | En español |
| `es_fin_de_semana` | Sábado o domingo |
| `temporada` | `PV` de marzo a agosto, `OI` de septiembre a febrero |
| `es_rebajas` | Del 7 de enero al 28 de febrero y del 1 de julio al 31 de agosto. Simplificación común a todos los países; documéntalo |
| `es_festivo` | 1 de enero, 1 de mayo y 25 de diciembre. Simplificación: el calendario no es por país |

---

## 6. Demo 3 · Catálogo y Athena sobre bronze

### 6.1 Infraestructura (`demo3-catalogo-athena/infra/`)

- **Bases de datos** de Glue `bronze` y `silver` (la segunda la usa la demo 4).
- **Crawler** `curso-bronze-cdc` sobre `s3://<bucket>/bronze/cdc/public/`:
  - Sin programación (se lanza en la demo).
  - Política de cambios de esquema: registrar y no borrar.
  - Exclusiones de la diapositiva de crawlers.
  - Rol IAM con lectura solo sobre `bronze/cdc/*`.
  - Debe crear las tablas `bronze.clientes` y `bronze.productos`.
- **Workgroup** `curso`:
  - Resultados en `s3://<bucket>/athena-results/` con cifrado SSE-S3.
  - `enforce_workgroup_configuration = true`.
  - Límite de 10 GB por consulta y métricas en CloudWatch.
  - `force_destroy = true`.
- **Sin** la tabla `bronze.ventas`: se crea en la demo desde el editor de Athena (paso 3 de la diapositiva). El script `athena.py` permite crearla también desde la terminal.

### 6.2 SQL (`demo3-catalogo-athena/sql/`)

- `01_bronze_ventas.sql`: el DDL con partition projection del anexo A, con el bucket real como marcador (`${bucket}`) que sustituye `athena.py`.
- `02_exploracion.sql`: las consultas de la diapositiva «Explorar bronze con Athena», parametrizadas por fecha.
- `03_iceberg_prueba.sql`: el ejemplo de la diapositiva «Athena e Iceberg» (crear `silver.ventas_prueba`, time travel, OPTIMIZE, VACUUM). Incluye el `DROP` de la tabla de prueba al final.

### 6.3 Scripts

- **`athena.py`:** ejecuta un fichero SQL o una consulta en el workgroup `curso`, espera el resultado y muestra filas y **bytes escaneados**.
- **`comprobar_demo3.py`:**
  - Las tablas `bronze.ventas`, `bronze.clientes` y `bronze.productos` existen.
  - Un recuento de un día de ventas coincide con las líneas en S3.
  - La consulta filtrada por partición escanea mucho menos que la que no filtra.

### 6.4 Criterios de aceptación (diapositiva «Qué comprobar» de la demo 3)

- [ ] **Athena lee los `.json.gz` de bronze.** Si `Content-Encoding: gzip` causara problemas, documenta la solución y anótala.
- [ ] Tres tablas en `bronze` con su esquema. El crawler crea `clientes` y `productos` con los tipos de `ESTADO_SESION1.md` §4.2.
- [ ] Las consultas filtradas por partición muestran «Data scanned» en KB o MB.
- [ ] Con `DUPLICADOS_PCT > 0`, `count(*) > count(DISTINCT event_id)`.
- [ ] Coste de la demo: céntimos.

---

## 7. Demo 4 · El pipeline de punta a punta

### 7.1 Tablas de silver (`demo4-pipeline/sql/athena/`, creadas con `crear_silver.py`)

Todas Iceberg (formato v2), en `s3://<bucket>/silver/<tabla>/`.

| Tabla | Columnas | Particionado |
|---|---|---|
| `silver.ventas` | `event_id`, `fecha_venta` (timestamp), `canal`, `tienda_id`, `ticket_id`, `linea`, `cliente_id`, `producto_id`, `unidades`, `precio_unitario` (decimal(12,2), moneda local), `moneda`, `importe_bruto` (decimal(12,2), EUR), `descuento` (decimal(12,2), EUR), `medio_pago`, `pais`, `fecha_carga` (timestamp) | `day(fecha_venta)` |
| `silver.ventas_cuarentena` | Columnas de bronze como string, más `motivo` y `fecha_carga` | `day(fecha_carga)` |
| `silver.dim_cliente` | `cliente_id`, `nombre`, `email`, `telefono`, `segmento`, `provincia`, `pais`, `fecha_alta`, `valid_from` (date), `valid_to` (date), `is_current`, `es_baja`, `ts_ultimo_cambio` (timestamp) | — |
| `silver.dim_producto` | `producto_id`, `modelo`, `color`, `talla`, `familia`, `temporada`, `precio_catalogo`, `coste_unitario`, `valid_from`, `valid_to`, `is_current`, `es_baja`, `ts_ultimo_cambio` | — |
| `silver.tiendas` | `tienda_id`, `nombre`, `pais`, `region`, `ciudad`, `formato`, `superficie_m2`, `es_online`, `moneda` | — |
| `silver.tipos_cambio` | `moneda`, `eur_por_unidad` (decimal(18,8)) | — |
| `silver.calendario` | Los campos de §5.3 | — |

`cargar_referencia.py` rellena `tiendas`, `tipos_cambio` y `calendario` desde `comun/` con Athena (`INSERT INTO … VALUES` por lotes). Es idempotente: vacía la tabla antes de cargar.

### 7.2 Job `bronze-a-silver-ventas` (`glue/bronze_a_silver_ventas.py`)

- **Configuración:**
  - Glue 5.0, PySpark, `--datalake-formats iceberg` y la configuración del catálogo Iceberg de las notas de la diapositiva «Anatomía de un Glue Job».
  - Bookmarks activados.
  - 2 workers G.1X.
  - Parámetros `BUCKET` y `FORZAR_FALLO` (por defecto `false`).
- **Lectura:** `from_options` sobre `s3://<bucket>/bronze/ventas/`, JSON, `recurse: true`, con `transformation_ctx`. Comprueba que los bookmarks reconocen los `.json.gz` y que la descompresión funciona.
- **Si no hay ficheros nuevos:**
  - Escribe el control (abajo) con `filas_leidas = 0`.
  - Hace `job.commit()` y termina **con éxito**. El pipeline horario no debe avisar de fallo cuando el generador está parado.
- **Transformación**, según el código de las diapositivas «Anatomía de un Glue Job» y «Ventas: limpiar, desduplicar y MERGE» (anexo A):
  - `fecha_venta` desde `event_ts`.
  - `pais` desde `tienda_id`.
  - Join con `silver.tipos_cambio` para pasar `importe_bruto` y `descuento` a EUR.
  - `dropDuplicates(["event_id"])`.
  - `MERGE … WHEN NOT MATCHED THEN INSERT`.
  - Ojo: `descuento` ya es el importe total de la línea.
- **Glue Data Quality**, según el código de la diapositiva «Glue Data Quality dentro del job»:
  - Filas `Passed` → MERGE en `silver.ventas`; filas `Failed` → `silver.ventas_cuarentena` con el motivo.
  - `DataFreshness` **no es crítica**: el histórico la incumple por diseño. Su resultado va al control.
  - **Regla crítica:** si más del 50 % de las filas falla, el job lanza un error (fuente rota). Es lo que dice la diapositiva: «el script lanza un error, el job falla».
- **Control para Step Functions:** escribe `s3://<bucket>/control/calidad/ventas/ultima.json` con:
  - `filas_leidas`, `filas_ok`, `filas_cuarentena` y `pct_cuarentena`;
  - el resultado de cada regla;
  - `ts_fin`.

  La máquina de estados lo lee para decidir (§7.5).
- **`FORZAR_FALLO = true`** lanza una excepción al principio. Sirve para el paso 6 de la demo.

### 7.3 Job `bronze-a-silver-maestros` (`glue/bronze_a_silver_maestros.py`)

Lee los Parquet de `bronze/cdc/public/clientes/` y `…/productos/` de S3 con bookmarks y aplica SCD2 sobre `silver.dim_cliente` y `silver.dim_producto`.

| Tabla | SCD2 (nueva versión) | SCD1 (sobrescribir la vigente) |
|---|---|---|
| clientes | `segmento`, `provincia`, `pais` | `nombre`, `email`, `telefono` |
| productos | `familia`, `temporada` | `precio_catalogo`, `coste_unitario`, `modelo`, `color`, `talla` |

**Reglas:**

- **Arranque** (silver vacío): las filas de la carga completa (`LOAD…`, sin `Op`) crean la primera versión con `valid_from = 1900-01-01`. Así las ventas del histórico encuentran versión aunque sean anteriores a `fecha_alta`.
- **Cambios:**
  - `ts_commit` se convierte a timestamp y `fecha_cambio = to_date(ts_commit)`.
  - `valid_to` es exclusivo y coincide con el `valid_from` de la versión siguiente; la vigente lleva `9999-12-31`.
  - `I` crea una versión con `valid_from = fecha_cambio`.
  - `U` con cambio SCD2 cierra la vigente y abre una nueva; `U` solo con cambios SCD1 actualiza la vigente.
  - `D` cierra la vigente con `es_baja = true` y no abre ninguna.
- **Trampa a evitar.** En la primera ejecución llegan juntos la carga completa y los cambios. Si se aplica «último cambio por clave» sobre todo el lote, C-17 acabaría con una sola versión Premium desde 1900. Hay que aplicar primero la carga completa y después los cambios **en orden de `ts_commit`**. Por ejemplo, agrupando por `ts_commit` y aplicando el patrón MERGE + INSERT de la diapositiva «SCD2 con MERGE sobre Iceberg» a cada grupo, o calculando las versiones con funciones de ventana antes del MERGE. Elige la forma más clara y explícala en comentarios.
- **Mismo día.** Si la versión vigente se abrió el mismo día que el nuevo cambio (`valid_from = fecha_cambio`), se actualiza en lugar de crear una versión de duración cero. Es una desviación permitida del código de la diapositiva: anótala.
- **Granularidad de día.** Las ventas del 28-10-2026 anteriores al cambio de C-17 (17:23) quedarán asociadas a la versión Premium. Es una limitación conocida: documéntala en el GUION y en `CAMBIOS_DIAPOSITIVAS.md` como nota, no como cambio.

**Tests locales obligatorios** (`glue/tests/`, con `pyspark` en `requirements-dev.txt`, versión alineada con Glue 5.0) sobre las funciones puras de `transformaciones.py`:

1. Arranque solo con la carga completa.
2. Carga completa y CDC en el mismo lote: C-17 con dos versiones (Standard 1900-01-01 → 2026-10-28, Premium 2026-10-28 → 9999-12-31), C-4001 nuevo desde 2026-10-28 y C-981 cerrado con `es_baja`.
3. Cambio solo SCD1 (email).
4. Dos cambios el mismo día.
5. Un cliente que vuelve a su segmento anterior.
6. Desduplicación de ventas y conversión a EUR (incluido JPY sin decimales).

El MERGE real sobre Iceberg se prueba contra AWS.

### 7.4 Redshift Serverless (`demo4-pipeline/infra/` y `sql/redshift/`)

**Infraestructura:**

- **Red:**
  - VPC propia con subredes públicas en las zonas que exija Redshift Serverless (compruébalo; suelen ser 3) e internet gateway.
  - Sin NAT.
  - Security group: 5439 solo desde el rango de IP de QuickSight en `eu-west-1` (compruébalo en la documentación de QuickSight) y desde `mi_ip`, detectada como en la demo 2.
- **Namespace y workgroup `hp-retail`:**
  - Base de datos `dev`.
  - Contraseña de administrador gestionada por Redshift en Secrets Manager.
  - `publicly_accessible = true`.
  - Capacidad base mínima admitida en la región (comprueba si es 4 u 8 RPU) y capacidad máxima 16.
  - **Límite de uso** diario de 10 RPU-horas con acción de desactivar.
- **Rol IAM por defecto del namespace:** lectura del Glue Data Catalog (`silver`) y de `s3://<bucket>/silver/*`.

**SQL (`sql/redshift/`, ejecutado por `desplegar_redshift.py` con la Data API, idempotente):**

| Fichero | Contenido |
|---|---|
| `01_esquemas.sql` | Esquema externo `silver` (anexo A, diapositiva «Leer silver desde Redshift») y esquema `gold` |
| `02_gold_tablas.sql` | Las tablas de la estrella (abajo) y la fila `-1` de `dim_cliente` |
| `03_sp_cargar_dimensiones.sql` | MERGE de `dim_cliente` y `dim_producto` desde silver (por `id` + `valid_from`), MERGE de `dim_tienda` (SCD1) y carga de `dim_fecha` |
| `04_sp_cargar_gold.sql` | El procedimiento del anexo A (DELETE de la ventana + INSERT de la diapositiva «Gold: cada venta enlaza con su versión SCD2»), `SECURITY DEFINER` |
| `05_vistas.sql` | `gold.mv_ventas_diarias` (anexo A) y `gold.v_dashboard_ventas` (abajo) |
| `06_usuarios.sql` | Usuario `quicksight_ro` (solo `SELECT` en `gold`) y el usuario de la Data API del rol de Step Functions (`"IAMR:<rol>"`) con `EXECUTE` sobre `sp_cargar_gold` |
| `07_permisos_demo.sql` | El rol `analista_asia` y la política RLS de la diapositiva «Gold en Redshift: permisos del propio motor», con `pais IN ('JP', 'CN')` |

**Tablas gold** (importes en EUR):

| Tabla | Columnas | Distribución y ordenación |
|---|---|---|
| `dim_cliente` | `cliente_sk` (`GENERATED BY DEFAULT AS IDENTITY`), `cliente_id`, `segmento`, `provincia`, `pais`, `valid_from`, `valid_to`, `is_current`. Fila `-1`: `cliente_id = 'N/D'`, `segmento = 'Desconocido'`, vigencia 1900-01-01 → 9999-12-31 | ALL; `cliente_id`, `valid_from` |
| `dim_producto` | `producto_sk` (IDENTITY), `producto_id`, `modelo`, `color`, `talla`, `familia`, `temporada`, `valid_from`, `valid_to`, `is_current` | KEY(`producto_sk`) |
| `dim_tienda` | `tienda_sk` (IDENTITY), `tienda_id`, `nombre`, `pais`, `region`, `ciudad`, `formato`, `superficie_m2` | ALL |
| `dim_fecha` | `fecha_sk` (`AAAAMMDD`) y los campos del calendario | ALL |
| `fct_ventas` | `fecha_sk`, `cliente_sk`, `producto_sk`, `tienda_sk`, `ticket_id`, `linea`, `unidades`, `importe_bruto`, `descuento` | KEY(`producto_sk`); `fecha_sk` |

**Vista `gold.v_dashboard_ventas`** (una fila por línea de venta, para QuickSight):

- `fecha`, `fecha_sk`, `anio`, `semana_iso`, `mes`, `es_rebajas`;
- `pais`, `region`, `tienda_id`;
- `familia`, `color`, `talla`;
- `segmento`;
- `clave_ticket` (`tienda_id || '-' || ticket_id`);
- `unidades` y `venta_neta` (`importe_bruto - descuento`).

**Carga inicial:** `cargar_gold_inicial.py` llama a `sp_cargar_gold` con la ventana completa del histórico. La máquina de estados, en cambio, carga solo ayer y hoy, como en la diapositiva.

### 7.5 Step Functions (`stepfunctions/pipeline.asl.json`)

Máquina **Standard** `curso-aws-hp-pipeline`. Sigue la diapositiva «Nuestra máquina de estados» y los fragmentos del anexo A:

1. **`SilverEnParalelo`** (Parallel): los dos jobs con `glue:startJobRun.sync`. Retry ×2 con backoff ante `States.TaskFailed`; Catch → `NotificarFallo`. Pasa a cada job el argumento `--FORZAR_FALLO` desde la entrada de la ejecución (por defecto `"false"`). Es una desviación permitida del fragmento de la diapositiva, que no muestra argumentos.
2. **`LeerCalidad`**: `aws-sdk:s3:getObject` del control de ventas y `States.StringToJson` en un `ResultSelector`.
3. **`CalidadOK`** (Choice):
   - Si `filas_leidas = 0`, va a `SinDatos` (Succeed).
   - Si `pct_cuarentena > 5`, va a `NotificarFallo`.
   - Si no, va a `CargarGold`.
4. **`CargarGold` → `EsperarGold` → `EstadoGold` → `GoldTerminado`**: el bucle con la Data API de la diapositiva «Cargar gold con la Redshift Data API» (`WorkgroupName: hp-retail`, `Database: dev`, autenticación IAM). Retry ×2 en `CargarGold`.
5. **`RefrescarSPICE`**: `aws-sdk:quicksight:createIngestion` con `IngestionId` generado con `States.UUID()`. Si QuickSight está desactivado (§7.6), este estado es un Pass.
6. **`NotificarOK`** y **`NotificarFallo`**: SNS al tema nuevo `curso-aws-hp-pipeline` (suscripción por email con `email_alertas`).

**Programación:** EventBridge Scheduler `cron(0 * * * ? *)`, zona `Europe/Madrid`, entrada `{"forzar_fallo": "false"}`, **desactivada** salvo con `programacion_activa = true`.

**Rol de la máquina** con permisos mínimos:

- Lanzar y consultar esos dos jobs.
- `s3:GetObject` del control.
- Redshift Data API sobre el workgroup y `redshift-serverless:GetCredentials`.
- `quicksight:CreateIngestion` sobre el dataset.
- `sns:Publish` sobre el tema.

### 7.6 QuickSight (`demo4-pipeline/infra/quicksight.tf`)

La suscripción de QuickSight **es manual** (prueba gratuita, ver la diapositiva de la suscripción) y es un requisito previo. Todo lo de QuickSight va detrás de la variable `quicksight_activo` (por defecto `false`) para poder aplicar el resto antes.

- **Variables:** `quicksight_usuario_arn` (el ARN del usuario Author del profesor) y `quicksight_activo`.
- **Fuente de datos** `curso-redshift-gold`:
  - Tipo Redshift, con host y puerto del endpoint público del workgroup y base de datos `dev`.
  - Credenciales del usuario `quicksight_ro` (contraseña con `random_password`, guardada también en Secrets Manager para los scripts).
  - SSL activado.
  - Permisos completos para `quicksight_usuario_arn`.
- **Dataset** `ventas_dashboard`:
  - Importación SPICE de `gold.v_dashboard_ventas`.
  - Campos calculados de fila en el dataset: `venta_rebajas = ifelse(es_rebajas, venta_neta, 0)`. Los agregados se crean en el análisis, como indica la diapositiva «Conectar QuickSight con gold».
  - Permisos para el mismo usuario.
- **Outputs:** `quicksight_dataset_id` y `quicksight_dataset_arn`, que usa la máquina de estados.

### 7.7 Infraestructura de Glue (`demo4-pipeline/infra/glue.tf`)

- **Scripts de los jobs** subidos con Terraform a `s3://<bucket>/artefactos/glue/` (`aws_s3_object` con `etag`), incluido `transformaciones.py` como `--extra-py-files`.
- **Rol de los jobs:**
  - Lectura de `bronze/ventas/*` y `bronze/cdc/*`.
  - Lectura y escritura de `silver/*` y `control/*`.
  - Lectura de `artefactos/*`.
  - Glue Data Catalog sobre `silver`.
  - CloudWatch Logs y métricas, y publicación de resultados de Data Quality.
- **Jobs** con `--job-bookmark-option job-bookmark-enable`, 2 workers G.1X y timeout de 30 min. Clase de ejecución por variable (`STANDARD` en la demo; `FLEX` para la programación horaria).
- **Opcional:** optimización automática de la tabla `silver.ventas` en el catálogo (compactación). Si complica el despliegue, documéntalo y déjalo fuera.

### 7.8 Criterios de aceptación (diapositiva «Qué comprobar» de la demo 4)

- [ ] El backfill y una ejecución del generador (`MODO=pico DUPLICADOS_PCT=5`, 10 min) están en bronze.
- [ ] Una ejecución manual de la máquina de estados termina en verde y el email de éxito llega.
- [ ] `silver.ventas` sin duplicados: `count(*) = count(DISTINCT event_id)`, e importes en EUR coherentes (un JPY de 6.392 ≈ 39,95 €).
- [ ] `silver.dim_cliente`:
  - C-17 con dos versiones;
  - C-4001 desde el 28-10-2026;
  - C-981 cerrado con `es_baja`.
- [ ] Gold:
  - `fct_ventas` cuadra con `silver.ventas` en la ventana cargada;
  - las ventas sin cliente apuntan a `cliente_sk = -1`;
  - `mv_ventas_diarias` y `v_dashboard_ventas` devuelven datos.
- [ ] El dataset de QuickSight se refresca desde la máquina de estados.
- [ ] Con `{"forzar_fallo": "true"}`: Catch → `NotificarFallo`, email de fallo y gold sin tocar.
- [ ] Una segunda ejecución sin datos nuevos termina en `SinDatos` sin error.
- [ ] El coste de una ejecución completa queda en céntimos y figura en el GUION.

---

## 8. Lake Formation (`demo4-pipeline/infra-lakeformation/`, solo el profesor)

Las diapositivas avisan a los alumnos de que **no lo activen en sus cuentas de empresa**. Este módulo lo aplica solo el profesor, en su cuenta de pruebas, y debe ser **reversible con `terraform destroy`** sin efectos en el resto de la cuenta.

**Precauciones obligatorias:**

- **Administradores del lago.** `aws_lakeformation_data_lake_settings` **sustituye** la configuración completa de la cuenta. Antes de aplicar:
  - lee la configuración actual con el data source;
  - **conserva los administradores existentes** y añade el principal del profesor (variable);
  - no cambies los permisos por defecto de bases de datos y tablas nuevas (`IAM_ALLOWED_PRINCIPALS` debe seguir).

  Muestra el diff y pregunta.
- **Modo de acceso híbrido.** Registra solo `s3://<bucket>/silver/` con `hybrid_access_enabled = true`. Los permisos de Lake Formation solo se aplican a los principales con *opt-in*: los dos roles de la demo. Los jobs de Glue, Redshift y los alumnos siguen con IAM.

**Recursos:**

- **Roles IAM** `curso-analista-asia` y `curso-data-science`, que el profesor puede asumir desde la consola (*switch role*). Permisos de Athena en el workgroup `curso`, Glue de solo lectura y escritura en `athena-results/`.
- **LF-Tags** de la diapositiva «LF-Tags: permisos basados en etiquetas»:
  - `capa` (`bronze`, `silver`) y `sensibilidad` (`publico`, `pii`);
  - `sensibilidad = pii` en `nombre`, `email` y `telefono` de `silver.dim_cliente`.
- **Filtro** `analistas_asia` sobre `silver.ventas`, con filas `pais IN ('JP', 'CN')` y sin `cliente_id` (anexo A).
- **Grants:**
  - `curso-analista-asia`: SELECT sobre el filtro.
  - `curso-data-science`: SELECT sobre `capa = silver` y `sensibilidad = publico`.
- **Opt-in** de los dos roles en el modo híbrido.

**Criterios:**

- [ ] Como `curso-analista-asia`, `SELECT * FROM silver.ventas` en Athena devuelve solo JP y CN y no muestra `cliente_id`.
- [ ] Como `curso-data-science`, `silver.dim_cliente` no muestra `nombre`, `email` ni `telefono`.
- [ ] El pipeline de la demo 4 sigue funcionando con el módulo aplicado.
- [ ] Tras `terraform destroy`, la configuración de Lake Formation vuelve a la original (comprobado con `aws lakeformation get-data-lake-settings` antes y después).

`GUION_LAKE_FORMATION.md` sigue el anexo C.

---

## 9. Guiones

- **`demo3-catalogo-athena/GUION.md`:**
  - Preparación: backfill y generador con duplicados.
  - Los seis pasos de la diapositiva de la demo 3. Los pasos 1 y 4 dicen «revisar», porque Terraform ya crea las bases de datos y el workgroup; explica en el guion cómo se crearían desde la consola.
  - Comandos, salida esperada y qué hacer si algo falla.
- **`demo4-pipeline/GUION.md`:**
  - **Preparación** antes de clase: `terraform apply` de infra, `crear_silver.py`, `cargar_referencia.py`, `desplegar_redshift.py`, primera ejecución del pipeline y `cargar_gold_inicial.py`, suscripción de QuickSight y `quicksight_activo = true`.
  - **Los seis pasos de la diapositiva** de la demo 4.
  - **El guion de QuickSight del anexo B**, con los nombres reales de menús comprobados en la consola.
  - **Limpieza:**
    - desactivar la programación;
    - Redshift se mantiene para la sesión 3 (sin consultas no hay cómputo);
    - recordar la fecha de fin de la prueba de QuickSight.
- **`demo4-pipeline/GUION_LAKE_FORMATION.md`:** anexo C.

Indica en cada paso el tiempo aproximado. Crear el workgroup de Redshift y el primer job de Glue tarda varios minutos: debe hacerse antes de la clase.

---

## 10. Plan de trabajo y reglas para Claude Code

### Reglas

- **Pregunta antes** de cualquier `terraform apply` o `destroy` y de cualquier acción que cree, modifique o borre recursos en AWS. Muestra el resumen del plan e indica qué recursos tienen coste por hora o por uso.
- **Lake Formation:** además del plan, muestra la configuración actual y la que quedará, y espera confirmación explícita.
- No toques recursos que no haya creado este repositorio.
- Mismas versiones que la sesión 1 salvo necesidad (`ESTADO_SESION1.md` §10). Añade `pyspark` a `requirements-dev.txt` alineado con Glue 5.0.
- `pytest`, `ruff`, `terraform fmt` y `terraform validate` en verde antes de dar algo por terminado, incluidos los de la sesión 1.

### Orden

1. **Pendiente de la sesión 1:** el log group de DMS (§3).
2. **`comun/`:**
   - extraer `eventos.py` del generador;
   - añadir `region` en `maestros.py` y crear `referencia.py`, con sus tests.
3. **`backfill_ventas.py`** y sus tests → **preguntar** → ejecutarlo en AWS.
4. **Demo 3:** infraestructura (plan → **preguntar** → apply), SQL, scripts y `comprobar_demo3.py` en verde. **Primero, comprobar que Athena lee los `.json.gz`.**
5. **Demo 4, silver:**
   - `transformaciones.py` con sus tests locales;
   - jobs de Glue;
   - infraestructura de Glue;
   - `crear_silver.py` y `cargar_referencia.py`;
   - ejecutar los dos jobs a mano y comprobar silver.
6. **Demo 4, gold:** Redshift (plan → **preguntar** → apply), `desplegar_redshift.py`, `cargar_gold_inicial.py` y comprobaciones.
7. **Demo 4, orquestación:** Step Functions, SNS y Scheduler (desactivado); ejecución manual, ejecución sin datos y ejecución con fallo forzado.
8. **QuickSight:** cuando el profesor confirme la suscripción y el ARN del usuario, `quicksight_activo = true`, dataset y refresco desde la máquina de estados.
9. **Lake Formation** (solo con confirmación expresa del profesor).
10. Guiones, README y `CAMBIOS_DIAPOSITIVAS.md`.
11. Actualiza `ESTADO_SESION1.md` o crea `ESTADO_SESION2.md` con el mismo formato, para preparar la sesión 3.

---

## 11. `CAMBIOS_DIAPOSITIVAS.md`

Mismo formato que en la sesión 1 (`diapositiva | texto actual | texto propuesto | motivo`), con una sección por sesión. Esta vez **se conserva en el repositorio**. Incluye al menos:

- Las desviaciones permitidas de este handoff:
  - argumentos `--FORZAR_FALLO`;
  - estado `LeerCalidad`;
  - versión del mismo día en SCD2;
  - umbral del 50 % / 5 %.
- Lo que no coincida al probar (nombres de campos, sintaxis, comportamiento de Athena con los `.json.gz`).
- La nota sobre la granularidad de día del SCD2.

Ya están aplicados en las diapositivas, para que no se repitan:

- demos renumeradas;
- workgroup `curso` con `athena-results/`;
- lectura de `bronze/ventas` desde S3;
- Asia = JP y CN;
- conexión de QuickSight sin VPC;
- `fct_stock_diario` fuera de alcance;
- advertencia de Lake Formation.

---

## 12. Fuera de alcance

- Sesión 3: ECS con Fargate, Batch, Cognito, GuardDuty, Inspector y SageMaker. Pero deja preparado para ella:
  - `gold.mv_ventas_diarias`;
  - el histórico de 120 días;
  - `silver.calendario`;
  - Redshift desplegado.
- `fct_stock_diario` y `fct_pedido_online`.
- La conexión VPC de QuickSight (se cita en las diapositivas como opción de producción).

---

## Anexo A · Código tal como aparece en las diapositivas de la sesión 2

Número de diapositiva y título. El código de las diapositivas a veces está simplificado (por ejemplo, sin imports o con una sola columna); el repositorio puede completarlo, pero no contradecirlo.

### Diapositiva 11 · Tabla de bronze con partition projection

```sql
CREATE EXTERNAL TABLE bronze.ventas (
  event_id string, event_ts string, canal string, tienda_id string,
  ticket_id string, linea int, cliente_id string, producto_id string,
  unidades int, precio_unitario double, descuento double,
  moneda string, medio_pago string)
PARTITIONED BY (anio string, mes string, dia string)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://retail-company-datalake-prod/bronze/ventas/'
TBLPROPERTIES (
  'projection.enabled'     = 'true',
  'projection.anio.type'   = 'integer', 'projection.anio.range' = '2024,2030',
  'projection.mes.type'    = 'integer', 'projection.mes.range'  = '1,12',
  'projection.mes.digits'  = '2',
  'projection.dia.type'    = 'integer', 'projection.dia.range'  = '1,31',
  'projection.dia.digits'  = '2',
  'storage.location.template' =
    's3://retail-company-datalake-prod/bronze/ventas/anio=${anio}/mes=${mes}/dia=${dia}/'
);
```

### Diapositiva 14 · Workgroups de Athena

```bash
# 1. Crear el workgroup (una vez, o con IaC)
aws athena create-work-group \
  --name curso \
  --configuration '{
    "ResultConfiguration": {
      "OutputLocation":
        "s3://retail-company-datalake-prod/athena-results/"
    },
    "EnforceWorkGroupConfiguration": true,
    "PublishCloudWatchMetricsEnabled": true,
    "BytesScannedCutoffPerQuery": 10737418240
  }'

# 2. Lanzar consultas en él
aws athena start-query-execution \
  --work-group curso \
  --query-string "SELECT count(*) FROM bronze.ventas"

# 3. Desde Python (boto3)
athena.start_query_execution(
    QueryString=sql, WorkGroup="curso")
```

### Diapositiva 15 · Explorar bronze con Athena

```sql
-- ¿Cuántos eventos y cuántos duplicados hoy?
SELECT count(*)                 AS eventos,
       count(DISTINCT event_id) AS unicos
FROM bronze.ventas
WHERE anio = '2026' AND mes = '10' AND dia = '24';

-- Top 5 productos por venta neta del día
SELECT producto_id,
       sum(unidades * precio_unitario
           - descuento)         AS venta_neta
FROM bronze.ventas
WHERE anio = '2026' AND mes = '10' AND dia = '24'
GROUP BY producto_id
ORDER BY venta_neta DESC
LIMIT 5;
```

### Diapositiva 16 · Athena e Iceberg

```sql
-- Crear una tabla Iceberg con particionado oculto
CREATE TABLE silver.ventas_prueba (
  event_id string, fecha_venta timestamp,
  tienda_id string, importe decimal(12,2))
PARTITIONED BY (day(fecha_venta))
LOCATION 's3://retail-company-datalake-prod/silver/prueba/'
TBLPROPERTIES ('table_type' = 'ICEBERG');

-- Time travel: la tabla hace una hora
SELECT count(*) FROM silver.ventas
FOR TIMESTAMP AS OF (current_timestamp - interval '1' hour);

-- Mantenimiento
OPTIMIZE silver.ventas REWRITE DATA USING BIN_PACK;
VACUUM silver.ventas;
```

### Diapositiva 21 · Anatomía de un Glue Job

```python
import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F

args = getResolvedOptions(sys.argv, ["JOB_NAME", "BUCKET"])
glue = GlueContext(SparkContext())
job = Job(glue)
job.init(args["JOB_NAME"], args)

# 1. Leer bronze directamente de S3 (solo ficheros nuevos)
dyf = glue.create_dynamic_frame.from_options(
    connection_type="s3", format="json",
    connection_options={
        "paths": [f"s3://{args['BUCKET']}/bronze/ventas/"],
        "recurse": True},
    transformation_ctx="bronze_ventas")  # bookmark
df = dyf.toDF()

# 2. Transformar con DataFrames de Spark
df = (df
    .dropDuplicates(["event_id"])                  # duplicados
    .withColumn("fecha_venta", F.to_timestamp("event_ts"))
    .withColumn("tienda_id", F.upper(F.trim("tienda_id")))
    .filter(F.col("unidades") >= 1))                # inválidos

# 3. Escribir en silver con Iceberg
job.commit()  # guarda el bookmark
```

### Diapositiva 24 · Ventas: limpiar, desduplicar y MERGE

```python
from pyspark.sql import functions as F
cambio = spark.table("glue_catalog.silver.tipos_cambio")

ventas = (df
  .withColumn("fecha_venta", F.to_timestamp("event_ts"))
  .withColumn("pais", F.substring("tienda_id", 1, 2))
  .filter("unidades >= 1 AND producto_id IS NOT NULL")
  .dropDuplicates(["event_id"])
  # importes a EUR: moneda -> eur_por_unidad
  .join(F.broadcast(cambio), "moneda")
  .withColumn("importe_bruto", (F.col("unidades")
      * F.col("precio_unitario") * F.col("eur_por_unidad"))
      .cast("decimal(12,2)"))
  .withColumn("descuento", (F.col("descuento")
      * F.col("eur_por_unidad")).cast("decimal(12,2)")))

ventas.createOrReplaceTempView("nuevas")

spark.sql("""
  MERGE INTO glue_catalog.silver.ventas t
  USING nuevas s
    ON t.event_id = s.event_id
  WHEN NOT MATCHED THEN INSERT *
""")
```

### Diapositiva 26 · SCD2 con MERGE sobre Iceberg

```sql
-- Paso 1: cerrar versiones que cambian y dar de alta los nuevos
MERGE INTO glue_catalog.silver.dim_cliente t
USING stg_clientes s
  ON t.cliente_id = s.cliente_id AND t.is_current = true
WHEN MATCHED AND (t.segmento <> s.segmento
               OR t.provincia <> s.provincia) THEN
  UPDATE SET t.valid_to   = s.fecha_cambio,
             t.is_current = false
WHEN NOT MATCHED THEN
  INSERT (cliente_id, segmento, provincia, email,
          valid_from, valid_to, is_current)
  VALUES (s.cliente_id, s.segmento, s.provincia, s.email,
          s.fecha_cambio, DATE '9999-12-31', true);

-- Paso 2: abrir la versión nueva de los que se acaban de cerrar
INSERT INTO glue_catalog.silver.dim_cliente
SELECT s.cliente_id, s.segmento, s.provincia, s.email,
       s.fecha_cambio, DATE '9999-12-31', true
FROM stg_clientes s
JOIN glue_catalog.silver.dim_cliente t
  ON  t.cliente_id = s.cliente_id
  AND t.is_current = false
  AND t.valid_to   = s.fecha_cambio;
```

### Diapositiva 27 · Mantenimiento de las tablas Iceberg

```sql
-- Compactar ficheros pequeños en ficheros de ~128 MB
CALL glue_catalog.system.rewrite_data_files(
  table   => 'silver.ventas',
  options => map('target-file-size-bytes', '134217728'));

-- Expirar snapshots de más de 7 días
CALL glue_catalog.system.expire_snapshots(
  table      => 'silver.ventas',
  older_than => TIMESTAMP '2026-10-17 00:00:00');

-- Borrar ficheros que ya no referencia ningún snapshot
CALL glue_catalog.system.remove_orphan_files(
  table => 'silver.ventas');
```

### Diapositiva 29 · Glue Data Quality dentro del job

```python
# 1. Reglas en DQDL
reglas = """Rules = [
  RowCount > 0,
  IsComplete "event_id",
  IsUnique "event_id",
  IsComplete "producto_id",
  ColumnValues "unidades" >= 1,
  ColumnValues "moneda" in ["EUR","USD","JPY","CNY"],
  DataFreshness "fecha_venta" <= 24 hours
]"""

# 2. Evaluar justo después de transformar
dq = EvaluateDataQuality().process_rows(
    frame=dyf_limpio, ruleset=reglas,
    publishing_options={
      "dataQualityEvaluationContext": "silver_ventas",
      "enableDataQualityCloudWatchMetrics": True})

# 3. Separar filas buenas y malas
filas = SelectFromCollection.apply(
    dq, key="rowLevelOutcomes").toDF()
ok = filas.filter(
    "DataQualityEvaluationResult = 'Passed'")
malas = filas.filter(
    "DataQualityEvaluationResult = 'Failed'")
```

### Diapositiva 36 · Leer silver desde Redshift

```sql
-- Silver visible en Redshift sin moverlo
CREATE EXTERNAL SCHEMA silver
FROM DATA CATALOG
DATABASE 'silver'
IAM_ROLE default;

-- Esquema de la capa gold
CREATE SCHEMA gold;

-- Comprobación
SELECT count(*)
FROM silver.ventas
WHERE fecha_venta >= current_date - 1;
```

### Diapositiva 38 · Gold: dim_cliente con clave subrogada

```sql
CREATE TABLE gold.dim_cliente (
  cliente_sk  BIGINT GENERATED BY DEFAULT AS IDENTITY(1,1),
  cliente_id  VARCHAR(20) NOT NULL,
  segmento    VARCHAR(20),
  provincia   VARCHAR(60),
  valid_from  DATE NOT NULL,
  valid_to    DATE NOT NULL,
  is_current  BOOLEAN NOT NULL
) DISTSTYLE ALL SORTKEY (cliente_id, valid_from);

CREATE TEMP TABLE stg AS
SELECT cliente_id, segmento, provincia,
       valid_from, valid_to, is_current
FROM silver.dim_cliente;

MERGE INTO gold.dim_cliente USING stg s
  ON  gold.dim_cliente.cliente_id = s.cliente_id
  AND gold.dim_cliente.valid_from = s.valid_from
WHEN MATCHED THEN UPDATE SET
  valid_to = s.valid_to, is_current = s.is_current
WHEN NOT MATCHED THEN INSERT
  (cliente_id, segmento, provincia, valid_from, valid_to, is_current)
  VALUES (s.cliente_id, s.segmento, s.provincia,
          s.valid_from, s.valid_to, s.is_current);
```

### Diapositiva 39 · Gold: cada venta enlaza con su versión SCD2

```sql
INSERT INTO gold.fct_ventas
SELECT TO_CHAR(v.fecha_venta, 'YYYYMMDD')::INT AS fecha_sk,
       COALESCE(c.cliente_sk, -1)          AS cliente_sk,
       p.producto_sk,
       t.tienda_sk,
       v.ticket_id, v.linea, v.unidades,
       v.importe_bruto, v.descuento
FROM silver.ventas v
LEFT JOIN gold.dim_cliente c
  ON  c.cliente_id = v.cliente_id
  AND v.fecha_venta >= c.valid_from
  AND v.fecha_venta <  c.valid_to
JOIN gold.dim_producto p
  ON  p.producto_id = v.producto_id
  AND v.fecha_venta >= p.valid_from
  AND v.fecha_venta <  p.valid_to
JOIN gold.dim_tienda t
  ON  t.tienda_id = v.tienda_id
WHERE v.fecha_venta >= p_desde AND v.fecha_venta < p_hasta;
```

### Diapositiva 40 · Procedimiento de carga y vista materializada

```sql
CREATE OR REPLACE PROCEDURE gold.sp_cargar_gold(
    p_desde TIMESTAMP, p_hasta TIMESTAMP)
AS $$
BEGIN
  CALL gold.sp_cargar_dimensiones();
  DELETE FROM gold.fct_ventas
   WHERE fecha_sk >= TO_CHAR(p_desde, 'YYYYMMDD')::INT
     AND fecha_sk <  TO_CHAR(p_hasta, 'YYYYMMDD')::INT;
  -- INSERT INTO gold.fct_ventas ... (diapositiva anterior)
END;
$$ LANGUAGE plpgsql;

CREATE MATERIALIZED VIEW gold.mv_ventas_diarias
AUTO REFRESH YES AS
SELECT f.fecha_sk, t.pais, p.familia, p.color, p.talla,
       SUM(f.unidades)                     AS unidades,
       SUM(f.importe_bruto - f.descuento)  AS venta_neta
FROM gold.fct_ventas f
JOIN gold.dim_tienda t   ON t.tienda_sk   = f.tienda_sk
JOIN gold.dim_producto p ON p.producto_sk = f.producto_sk
GROUP BY 1, 2, 3, 4, 5;
```

### Diapositiva 46 · Filtro de filas y columnas

```json
// filtro-asia.json
{
  "TableCatalogId": "123456789012",
  "DatabaseName": "silver",
  "TableName": "ventas",
  "Name": "analistas_asia",
  "RowFilter": {
    "FilterExpression": "pais IN ('JP', 'CN')"
  },
  "ColumnWildcard": {
    "ExcludedColumnNames": ["cliente_id"]
  }
}

$ aws lakeformation create-data-cells-filter \
    --table-data file://filtro-asia.json
```

### Diapositiva 47 · Gold en Redshift: permisos del propio motor

```sql
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
```

### Diapositiva 56 · Fragmento de la máquina: silver en paralelo

```json
"SilverEnParalelo": {
  "Type": "Parallel",
  "Branches": [
    { "StartAt": "JobVentas", "States": { "JobVentas": {
        "Type": "Task",
        "Resource": "arn:aws:states:::glue:startJobRun.sync",
        "Parameters": { "JobName": "bronze-a-silver-ventas" },
        "End": true } } },
    { "StartAt": "JobMaestros", "States": { "JobMaestros": {
        "Type": "Task",
        "Resource": "arn:aws:states:::glue:startJobRun.sync",
        "Parameters": { "JobName": "bronze-a-silver-maestros" },
        "End": true } } }
  ],
  "Retry": [{ "ErrorEquals": ["States.TaskFailed"],
              "IntervalSeconds": 60, "MaxAttempts": 2,
              "BackoffRate": 2 }],
  "Catch": [{ "ErrorEquals": ["States.ALL"],
              "Next": "NotificarFallo" }],
  "Next": "CalidadOK"
}
```

### Diapositiva 57 · Cargar gold con la Redshift Data API

```json
"CargarGold": {
  "Type": "Task",
  "Resource":
    "arn:aws:states:::aws-sdk:redshiftdata:executeStatement",
  "Parameters": {
    "WorkgroupName": "hp-retail", "Database": "dev",
    "Sql": "CALL gold.sp_cargar_gold(current_date-1, current_date+1)"
  },
  "Next": "EsperarGold" },
"EsperarGold": { "Type": "Wait", "Seconds": 15,
                 "Next": "EstadoGold" },
"EstadoGold": {
  "Type": "Task",
  "Resource":
    "arn:aws:states:::aws-sdk:redshiftdata:describeStatement",
  "Parameters": { "Id.$": "$.Id" },
  "Next": "GoldTerminado" },
"GoldTerminado": {
  "Type": "Choice",
  "Choices": [
    { "Variable": "$.Status", "StringEquals": "FINISHED",
      "Next": "RefrescarSPICE" },
    { "Variable": "$.Status", "StringEquals": "FAILED",
      "Next": "NotificarFallo" } ],
  "Default": "EsperarGold" }
```

Notas de la diapositiva 21 (parámetros del job para Iceberg): `--datalake-formats iceberg`; `--conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions`, `spark.sql.catalog.glue_catalog=org.apache.iceberg.spark.SparkCatalog`, `spark.sql.catalog.glue_catalog.warehouse=s3://<bucket>/silver/`, `spark.sql.catalog.glue_catalog.catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog`, `spark.sql.catalog.glue_catalog.io-impl=org.apache.iceberg.aws.s3.S3FileIO`; `--job-bookmark-option job-bookmark-enable`.

---

## Anexo B · Guion de QuickSight para la demo 4

Borrador para `demo4-pipeline/GUION.md`. Los nombres de menús de la consola de Amazon Quick cambian con frecuencia: **compruébalos en la cuenta de pruebas** y ajusta el texto. Terraform ya ha creado la fuente de datos `curso-redshift-gold` y el dataset `ventas_dashboard` (SPICE). El resto se hace a mano en clase, en unos 15 minutos.

### B.1 Antes de la clase (una vez)

1. **Activar la prueba gratuita** de Amazon Quick en la región `eu-west-1`, con el email del profesor como administrador (rol Author). Anotar la fecha de fin de la prueba. No activar usuarios Pro ni las preguntas en lenguaje natural (ver la diapositiva «Suscripción de QuickSight para el curso»).
2. **Copiar el ARN del usuario** (Administrar cuenta → Usuarios, o `aws quicksight list-users`) en `quicksight_usuario_arn` del `terraform.tfvars` de `demo4-pipeline/infra/`, poner `quicksight_activo = true` y aplicar.
3. **Comprobar** que el dataset `ventas_dashboard` aparece en Datasets con estado de importación correcto y el número de filas esperado.

### B.2 En clase: del dataset al dashboard

1. **Ver el dataset.** Abrir `ventas_dashboard`:
   - Mostrar que es SPICE: tamaño e historial de actualizaciones.
   - Mostrar el campo calculado de fila `venta_rebajas`.
   - Explicar por qué los agregados no van aquí (diapositiva «Conectar QuickSight con gold»).
2. **Crear el análisis.** «Usar en análisis» (o Análisis → Nuevo análisis → `ventas_dashboard`), con una hoja interactiva.
3. **Campos calculados del análisis:**
   - `ticket_medio = sum(venta_neta) / distinctCount(clave_ticket)`.
   - `pct_rebajas = sum(venta_rebajas) / sum(venta_neta)`, con formato de porcentaje.
4. **Cuatro KPI** (tipo de visual KPI), en una fila:
   - **Venta neta:** `venta_neta` (suma), formato moneda EUR.
   - **Unidades:** `unidades` (suma).
   - **Ticket medio:** `ticket_medio`.
   - **% en rebajas:** `pct_rebajas`.
5. **Gráfico de líneas «Venta neta semanal por país»:**
   - Eje X: `fecha`, agregada por semana.
   - Valor: `venta_neta` (suma).
   - Color: `pais`.
   - Hay unos 120 días de histórico: se ven las rebajas de verano.
6. **Barras horizontales «Unidades por color»:**
   - Eje Y: `color`; valor: `unidades` (suma), ordenado de mayor a menor.
   - Filtro solo en este visual: `familia = vestidos`.
7. **Filtros y controles** para `fecha` (rango), `pais`, `familia` y `segmento`, cada filtro añadido como control en la parte superior de la hoja y aplicado a todos los visuales.
8. **Publicar** como dashboard `Ventas retail · curso`. Mostrar opcionalmente cómo se comparte con un lector y cómo se programa un informe por email, sin hacerlo.
9. **Cerrar el ciclo:**
   - Lanzar el generador unos minutos y ejecutar la máquina de estados.
   - Ver que el estado `RefrescarSPICE` crea una actualización del dataset.
   - Recargar el dashboard: la venta de hoy ha cambiado.

### B.3 Si algo falla

- **El dataset no importa:** probar la fuente de datos (Validar conexión). El fallo más habitual es el security group: comprueba que el rango de IP de QuickSight de `eu-west-1` está permitido en el puerto 5439 y que el workgroup es accesible públicamente.
- **El dashboard no cambia tras el pipeline:**
  - Mira el historial de actualizaciones del dataset.
  - Si la ingesta falló, mira el error en Step Functions (`RefrescarSPICE`).
  - Comprueba que el dataset es el mismo ID que recibe la máquina.
- **«% en rebajas» sale 0:** el filtro de fecha deja fuera julio y agosto.

### B.4 Al terminar el curso

Cancelar la suscripción en la administración de la cuenta antes de que acabe la prueba. Exportar antes lo que interese: se pierden análisis y dashboards. Poner `quicksight_activo = false` y aplicar antes de cancelar, para que Terraform no quede apuntando a recursos borrados.

---

## Anexo C · Guion de la demo de Lake Formation (solo el profesor)

Borrador para `demo4-pipeline/GUION_LAKE_FORMATION.md`. Unos 10 minutos. Va después de las diapositivas de Lake Formation y antes del ejercicio C.

### C.1 Antes de la clase

1. En la cuenta de pruebas, guardar la configuración actual: `aws lakeformation get-data-lake-settings > lf-antes.json`.
2. Aplicar `demo4-pipeline/infra-lakeformation/` (revisar el diff de administradores antes de confirmar).
3. Comprobar los criterios de §8 con los dos roles.

### C.2 En clase

1. **Recordar la advertencia** de la diapositiva «Lake Formation en una cuenta de empresa»: lo hace el profesor en una cuenta de pruebas y los alumnos no lo activan en sus cuentas.
2. **Consola de Lake Formation:**
   - administradores del lago;
   - ubicación `silver/` registrada en modo híbrido;
   - los dos roles con *opt-in*.
3. **LF-Tags:** `capa` y `sensibilidad`, y las columnas `nombre`, `email` y `telefono` de `silver.dim_cliente` marcadas como `pii`.
4. **Filtro de datos `analistas_asia`:** filas `pais IN ('JP', 'CN')` y columnas sin `cliente_id`. Relacionarlo con el JSON de la diapositiva «Filtro de filas y columnas».
5. **Cambiar al rol `curso-analista-asia`** (*switch role*), abrir Athena en el workgroup `curso` y consultar `SELECT pais, count(*) FROM silver.ventas GROUP BY pais`: solo JP y CN. `SELECT *`: no aparece `cliente_id`.
6. **Cambiar al rol `curso-data-science`** y consultar `silver.dim_cliente`: no aparecen `nombre`, `email` ni `telefono`.
7. **Volver al rol del profesor:** la misma consulta ve todo. El modo híbrido solo restringe a los principales con *opt-in*; los jobs de Glue y Redshift siguen funcionando con IAM.
8. **Enlazar con el ejercicio C** (matriz de permisos).

### C.3 Después de la clase

`terraform destroy` del módulo y comprobar que `aws lakeformation get-data-lake-settings` coincide con `lf-antes.json`.
