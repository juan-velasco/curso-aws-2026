# Estado del repositorio al cerrar la sesión 1

Punto de partida para preparar el handoff de la sesión 2. Recoge el estado **real** del repositorio y de la cuenta de pruebas el 30-10-2026, comprobado con Terraform, AWS CLI y boto3 (solo lecturas). Commit de referencia: `25d037c`.

Donde aparece `<ID de cuenta>`, el valor real se obtiene con `terraform -chdir=infra/base output -raw account_id`.

---

## 1. Árbol del repositorio

Ficheros versionados en git. No incluye `.terraform/`, `__pycache__/`, `.venv/`, estados de Terraform, `terraform.tfvars` ni `salida/`, que están en `.gitignore`.

```
curso_aws_hp/
├── .dockerignore                    # contexto de construcción del generador (raíz): solo comun/ y generador/
├── .gitignore
├── HANDOFF.md                       # especificación de la sesión 1
├── README.md
├── pyproject.toml                   # configuración de pytest y ruff (no es un paquete instalable)
├── requirements.txt                 # scripts de apoyo: boto3, psycopg, pyarrow
├── requirements-dev.txt             # requirements.txt + API + generador + pytest, moto, ruff
├── comun/
│   ├── __init__.py
│   ├── maestros.py                  # datos maestros deterministas
│   └── terraform.py                 # outputs(modulo): lee `terraform output -json` desde los scripts
├── infra/
│   └── base/
│       ├── .terraform.lock.hcl
│       ├── main.tf                  # bucket del lago, lifecycle, Budgets
│       ├── outputs.tf
│       ├── terraform.tfvars.ejemplo
│       ├── variables.tf
│       └── versions.tf
├── demo1-ingesta/
│   ├── GUION.md
│   ├── docker-compose.yml
│   ├── api/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   └── main.py              # FastAPI: POST /ventas/lote, GET /health
│   │   └── tests/
│   │       ├── conftest.py
│   │       └── test_api.py
│   ├── generador/
│   │   ├── Dockerfile               # se construye desde la raíz (context: ..)
│   │   ├── generador.py
│   │   ├── requirements.txt
│   │   └── tests/
│   │       ├── test_generador.py
│   │       └── test_maestros.py
│   ├── infra/
│   │   ├── .terraform.lock.hcl
│   │   ├── main.tf                  # Firehose, IAM, logs, alarma, SNS
│   │   ├── outputs.tf
│   │   ├── terraform.tfvars.ejemplo
│   │   ├── variables.tf
│   │   └── versions.tf
│   └── scripts/
│       ├── comprobar_bronze.py
│       └── evento_invalido.py
└── demo2-cdc-dms/
    ├── GUION.md
    ├── infra/
    │   ├── .terraform.lock.hcl
    │   ├── dms.tf                   # roles de DMS, secreto, instancia, endpoints, tarea
    │   ├── outputs.tf
    │   ├── rds.tf                   # remote_state de base, parameter group, RDS
    │   ├── red.tf                   # VPC, subredes, IGW, endpoint S3, security groups
    │   ├── terraform.tfvars.ejemplo
    │   ├── variables.tf
    │   └── versions.tf
    ├── scripts/
    │   ├── conexion.py              # utilidades: outputs, sesión boto3, conexión psycopg
    │   ├── cargar_semilla.py
    │   ├── tarea_dms.py             # probar | iniciar | estado | parar
    │   ├── aplicar_cambios.py
    │   └── comprobar_cdc.py
    └── sql/
        ├── 01_esquema.sql
        ├── 02_usuario_dms.sql
        └── 03_cambios_demo.sql
```

`CAMBIOS_DIAPOSITIVAS.md`, que pedía el handoff, se borró después de aplicar los cambios a las diapositivas. `HANDOFF.md` lo sigue mencionando en §3, §8 y §9.

---

## 2. Terraform: módulos, outputs y cómo comparten datos

| Módulo | Estado actual | Lee de |
|---|---|---|
| `infra/base` | Desplegado (6 recursos + 1 data source) | — |
| `demo1-ingesta/infra` | Desplegado (9 recursos + data sources) | `infra/base` por `terraform_remote_state` |
| `demo2-cdc-dms/infra` | **Destruido** (estado vacío) | `infra/base` por `terraform_remote_state` |

**Cómo se comparten los datos.** Cada módulo tiene su **estado local** (`terraform.tfstate` en su carpeta), sin backend remoto. Las demos leen la base con:

```hcl
data "terraform_remote_state" "base" {
  backend = "local"
  config  = { path = "${path.module}/../../infra/base/terraform.tfstate" }
}
```

De ahí sacan `region`, `bucket_name` y `bucket_arn`. Por eso hay que aplicar la base primero y no mover su carpeta. Los scripts de Python leen los outputs con `comun/terraform.py`, que ejecuta `terraform output -json` en la carpeta del módulo.

**Región y perfil.**
- La región es `eu-west-1`. Solo se define en `infra/base` (variable `region`) y los demás módulos la heredan de su estado.
- El perfil es `curso` por defecto (variable `perfil` en los tres módulos). En la cuenta de pruebas se usó `perfil = "default"` en los `terraform.tfvars`, que no están en git.
- Scripts y Docker usan `AWS_PROFILE`, también con `curso` por defecto. El compose lo lee con `${AWS_PROFILE:-curso}`.

### Outputs

| Módulo | Output | Contenido |
|---|---|---|
| `infra/base` | `bucket_name` | `retail-company-datalake-prod-<ID de cuenta>` |
| | `bucket_arn` | `arn:aws:s3:::retail-company-datalake-prod-<ID de cuenta>` |
| | `region` | `eu-west-1` |
| | `account_id` | ID de la cuenta |
| `demo1-ingesta/infra` | `stream_name` | `hp-retail-ventas` |
| | `stream_arn` | `arn:aws:firehose:eu-west-1:<ID de cuenta>:deliverystream/hp-retail-ventas` |
| | `bucket_name` | El de la base |
| | `region` | `eu-west-1` |
| | `politica_put_arn` | `arn:aws:iam::<ID de cuenta>:policy/api-ventas-firehose-put` |
| `demo2-cdc-dms/infra` (al recrearlo) | `rds_endpoint`, `rds_port`, `db_name` (`retail`), `usuario_maestro` (`retail_admin`) | Conexión a RDS |
| | `password_maestra` | **Sensible** (`terraform output -raw password_maestra`) |
| | `secreto_nombre` | `curso-aws-hp/demo2/dms-user` |
| | `tarea_arn`, `instancia_replicacion_arn`, `endpoint_origen_arn`, `endpoint_destino_arn` | ARN de DMS |
| | `bucket_name`, `region` | De la base |
| | `psql` | Comando de conexión sin contraseña |

### Variables principales

| Módulo | Variable | Defecto |
|---|---|---|
| `infra/base` | `region` | `eu-west-1` |
| | `perfil` | `curso` |
| | `sufijo_bucket` | `""` (= ID de cuenta) |
| | `email_alertas` | Obligatoria |
| | `presupuesto_usd` | `10` |
| `demo1-ingesta/infra` | `perfil` | `curso` |
| | `stream_name` | `hp-retail-ventas` |
| | `email_alertas` | `""` (= alarma sin SNS) |
| `demo2-cdc-dms/infra` | `perfil` | `curso` |
| | `mi_ip` | `""` (= detección con checkip.amazonaws.com) |
| | `crear_roles_dms` | `true` |
| | `version_postgres` | `17` |
| | `version_dms` | `3.6.1` |
| | `clase_dms` | `dms.t3.small` |
| | `cidr_vpc` | `10.20.0.0/16` |

Etiquetas por `default_tags` del proveedor: `proyecto = curso-aws-hp`, `sesion = 1` y `demo = base | demo1 | demo2`.

---

## 3. Rutas reales en S3

Bucket `retail-company-datalake-prod-<ID de cuenta>`: bloqueo de acceso público, SSE-S3, versionado activo y `force_destroy = true`.

| Uso | Ruta | Ejemplo real |
|---|---|---|
| Ventas (bronze) | `bronze/ventas/anio=AAAA/mes=MM/dia=DD/` | `bronze/ventas/anio=2026/mes=10/dia=28/hp-retail-ventas-1-2026-10-28-17-08-59-6c878343-4b7a-495f-9315-fbb220bcb041.json.gz` |
| Errores de Firehose | `errors/ventas/<error-output-type>/AAAA/MM/DD/` | Vacío: no hubo errores. Firehose usa el mismo patrón de nombre que en bronze |
| CDC, carga completa | `bronze/cdc/public/<tabla>/` (sin carpeta de fecha) | `bronze/cdc/public/clientes/LOAD00000001.parquet`, `bronze/cdc/public/productos/LOAD00000001.parquet` |
| CDC, cambios | `bronze/cdc/public/<tabla>/AAAA/MM/DD/` | `bronze/cdc/public/clientes/2026/10/28/20261028-172434489.parquet` |
| Athena (sesión 2) | `athena-results/` | Aún no existe. El lifecycle ya lo expira a los 7 días |

**Detalles que importan en la sesión 2:**
- **Fecha de la carpeta de ventas.** Las particiones `anio=/mes=/dia=` usan la fecha de **llegada** a Firehose (`!{timestamp}`, UTC), no `event_ts`.
- **Ficheros de ventas.** Son gzip reales (empiezan por `1f 8b`) con extensión `.json.gz` y metadatos `Content-Type: application/octet-stream` y `Content-Encoding: gzip`. Por ese `Content-Encoding`, al descargarlos desde la consola el navegador los guarda ya descomprimidos. Athena y Glue leen los bytes tal cual. La lectura con Athena **no se ha probado** (habría que crear una tabla en Glue).
- **Nombre de los ficheros CDC.** Siguen el patrón `AAAAMMDD-HHMMSSmmm.parquet`.
- **Lifecycle.**
  - `bronze/`: Standard-IA a 30 días, Glacier IR a 90 y Deep Archive a 365.
  - Versiones no actuales de todo el bucket: expiran a 30 días; las subidas multiparte incompletas se abortan a 7.
  - `athena-results/`: expira a 7 días.

---

## 4. Esquema real de los datos en bronze

### 4.1 Ventas (JSON Lines, un evento por línea)

Comprobado sobre los 1.803 eventos de bronze. El orden de los campos es siempre el de la tabla.

| Campo | Tipo JSON | Nulos | Formato / ejemplo |
|---|---|---|---|
| `event_id` | string | No | UUID v4: `32970ca7-b18f-49a2-b622-0f1482919ae3` |
| `event_ts` | string | No | UTC, milisegundos y `Z`: `2026-10-28T17:06:04.965Z` |
| `canal` | string | No | `TPV` (tienda física), `WEB` o `APP` (online) |
| `tienda_id` | string | No | `CN-SZX-001`, `ES-VLC-003`, `ONL-ES` |
| `ticket_id` | string | No | `T-<AAAAMMDD>-<nº tienda, 3 díg.>-<secuencia, 6 díg.>`, con `000` online: `T-20261028-001-061565` |
| `linea` | integer | No | 1–4, correlativa dentro del ticket |
| `cliente_id` | string o null | **Sí** (~30 % de los tickets) | `C-875` (sin ceros a la izquierda) |
| `producto_id` | string | No | `P-0928-AZU-M` |
| `unidades` | integer | No | 1 (88 %), 2 o 3 |
| `precio_unitario` | number | No | En moneda local. JPY sin decimales pero serializado como `6392.0` |
| `descuento` | number | No | Importe total de la línea (no unitario), 0 o entre el 10 % y el 30 % de `precio_unitario × unidades` |
| `moneda` | string | No | `EUR`, `USD`, `JPY`, `CNY` |
| `medio_pago` | string | No | Tienda: `TARJETA`, `EFECTIVO`, `MOVIL`. Online: `TARJETA`, `PAYPAL` |

Ejemplo real:

```json
{"event_id": "32970ca7-b18f-49a2-b622-0f1482919ae3", "event_ts": "2026-10-28T17:06:04.965Z", "canal": "TPV", "tienda_id": "CN-SZX-001", "ticket_id": "T-20261028-001-061565", "linea": 1, "cliente_id": "C-875", "producto_id": "P-0928-AZU-M", "unidades": 1, "precio_unitario": 335.01, "descuento": 74.03, "moneda": "CNY", "medio_pago": "EFECTIVO"}
```

Para la sesión 2:
- **`ticket_id` no es único entre tiendas.** El número de tienda solo es único dentro de un país (`ES-MAD-001` y `FR-PAR-001` comparten `001`), así que la clave de ticket es `(tienda_id, ticket_id)`.
- **La secuencia de ticket arranca en los segundos transcurridos del día (UTC).** Así no se repiten tickets entre ejecuciones sucesivas del mismo día.
- **Todas las líneas de un ticket comparten** `event_ts`, `cliente_id` y `medio_pago`.

### 4.2 CDC de DMS (Parquet 2.6, `created_by AWS`)

**`clientes`**: tanto en LOAD como en CDC.

| Columna | Tipo Arrow | Tipo físico Parquet | Nulos | Notas |
|---|---|---|---|---|
| `Op` | string | BYTE_ARRAY (STRING) | Sí | **Solo en los ficheros CDC** y como **primera** columna: `I`, `U`, `D`. No existe en LOAD |
| `ts_commit` | **string** | BYTE_ARRAY (STRING) | No | Formato `2026-10-28 17:23:34.470161` (microsegundos, sin zona, UTC). **No es un timestamp**: hay que convertirlo con `CAST` o `to_timestamp` |
| `cliente_id` | string | BYTE_ARRAY | Sí* | |
| `nombre` | string | | Sí* | |
| `email` | string | | Sí* | |
| `telefono` | string | | Sí* | |
| `segmento` | string | | Sí* | `Standard` / `Premium` |
| `provincia` | string | | Sí* | |
| `pais` | string | | Sí* | |
| `fecha_alta` | date32[day] | INT32 (DATE) | Sí* | |
| `actualizado_en` | timestamp[ms, tz=UTC] | INT64 | Sí* | Milisegundos (`parquet_timestamp_in_millisecond = true`) |

\* DMS declara todas las columnas de datos como *nullable* aunque en PostgreSQL sean `NOT NULL`.

**`productos`**: solo hay LOAD, porque la demo no cambió productos.

| Columna | Tipo Arrow | Notas |
|---|---|---|
| `ts_commit` | string (not null) | Igual que en clientes |
| `producto_id`, `modelo`, `color`, `talla`, `familia`, `temporada` | string | `modelo` son 4 dígitos con ceros (`0412`) y `color` es el nombre (`Rojo`) |
| `precio_catalogo` | **decimal128(8, 2)** | `numeric(8,2)` en PostgreSQL. EUR |
| `coste_unitario` | **decimal128(8, 2)** | EUR |

**Contenido del CDC**: un fichero con 3 filas de la misma transacción, que comparten `ts_commit`.

| Op | cliente_id | segmento | provincia | ts_commit |
|---|---|---|---|---|
| U | C-17 | Premium | Valencia | 2026-10-28 17:23:34.470161 |
| I | C-4001 | Standard | Lyon | 2026-10-28 17:23:34.470161 |
| D | C-981 | Standard | Madrid | 2026-10-28 17:23:34.470161 |

Las tablas tienen `REPLICA IDENTITY FULL`, así que la fila `D` llega con **todas** las columnas de la fila borrada, no solo con la clave. Para reconstruir el estado en silver: última fila por `cliente_id` ordenada por `ts_commit` convertido a timestamp, sobre la unión de LOAD y CDC, descartando las `D`.

---

## 5. Volumen generado en las pruebas

### Demo 1 (contra AWS)

| Dato | Valor |
|---|---|
| Ejecución | 1, `MODO=pico` (10 eventos/s) durante **3 min** (la demo de clase son 10), de 17:06:04 a 17:09:04 UTC del 28-10-2026 |
| Ficheros en `bronze/ventas/` | **7** `.json.gz`, 82.382 B en total, uno cada ~30 s (mediana 30 s) |
| Eventos en bronze | **1.803** líneas = 1.803 aceptados por la API = 1.803 `event_id` distintos |
| Duplicados | **0** (`DUPLICADOS_PCT=0`) |
| Inválidos | **0** en bronze. Los eventos inválidos se enviaron a mano (`evento_invalido.py` y `curl`): se rechazaron con 422 y no llegan a Firehose |
| Errores de entrega | 0 ficheros en `errors/` |
| `DataFreshness` | Máximo de 32 s |
| Reparto | Canal: TPV 968, APP 420, WEB 415. Moneda: EUR 793, JPY 401, USD 319, CNY 290. 537 líneas sin `cliente_id` |

Todos los eventos están en una sola partición (`dia=28`). **Para la sesión 2 conviene generar más volumen**: varios días, `DUPLICADOS_PCT > 0` para practicar la desduplicación y la ejecución de 10 min.

En local (moto) también se probaron duplicados (5 %) e inválidos (2 %), con recuentos correctos. Esos datos no están en AWS.

### Demo 2 (contra AWS)

| Fichero | Filas |
|---|---|
| `clientes/LOAD00000001.parquet` | 4.000 (571.192 B) |
| `productos/LOAD00000001.parquet` | 1.200 (116.731 B) |
| `clientes/2026/10/28/20261028-172434489.parquet` | 3 (U, I, D), 2.989 B |

El fichero CDC apareció **61 s** después del `COMMIT`.

---

## 6. Qué sigue desplegado y qué se destruyó

**Desplegado** (sin coste por hora):

| Recurso | Módulo |
|---|---|
| S3 `retail-company-datalake-prod-<ID de cuenta>` y su configuración (acceso público, cifrado, versionado, lifecycle) | base |
| AWS Budgets `curso-aws-hp-mensual` (10 USD; gasto real del mes 0,04 USD) | base |
| Firehose `hp-retail-ventas` | demo1 |
| Rol `firehose-hp-retail-ventas` y su política inline `escritura-bronze-ventas` | demo1 |
| Política gestionada `api-ventas-firehose-put` | demo1 |
| Log group `/aws/kinesisfirehose/hp-retail-ventas` (7 días) y log stream `DestinationDelivery` | demo1 |
| Alarma `hp-retail-ventas-data-freshness` | demo1 |
| SNS `hp-retail-ventas-alertas` con suscripción por email **confirmada** | demo1 |

**Destruido** con `terraform destroy` del módulo demo2 (30 recursos, sin intervención manual):
- RDS `curso-aws-hp-retail`, con su parameter group y subnet group. Sin snapshot final (`skip_final_snapshot`).
- Instancia de replicación `curso-aws-hp-demo2`, su subnet group, los dos endpoints y la tarea.
- Secreto `curso-aws-hp/demo2/dms-user` (borrado inmediato, sin ventana de recuperación).
- VPC, subredes, IGW, tabla de rutas, endpoint de S3 y security groups.
- Roles `dms-vpc-role`, `dms-cloudwatch-logs-role`, `curso-aws-hp-dms-secreto` y `curso-aws-hp-dms-s3`.

Comprobado: 0 instancias de DMS, 0 endpoints, 0 instancias RDS, 0 snapshots, 0 VPC del proyecto y 0 secretos `curso-*`.

**Los ficheros de `bronze/cdc/` siguen en el bucket** (los 3 Parquet de arriba): están en el bucket de la base, que no se destruye.

**Restos fuera de Terraform:**
- **Log group `dms-tasks-curso-aws-hp-demo2`** (23 KB, sin retención). Lo crea DMS al activar el logging de la tarea y Terraform no lo gestiona, así que el `destroy` no lo borra. Coste despreciable, pero contradice el criterio «destroy elimina todo». Opciones: declararlo en `dms.tf` como `aws_cloudwatch_log_group` con retención, o borrarlo a mano. **Pendiente de decidir.**
- El log group `RDSOSMetrics` de la cuenta es de 2019: no lo creó este repositorio.

---

## 7. Roles y políticas IAM

| Nombre | Tipo | Módulo | Para qué | Estado |
|---|---|---|---|---|
| `firehose-hp-retail-ventas` | Rol (confianza: `firehose.amazonaws.com` con `sts:ExternalId` = ID de cuenta) | demo1 | Que Firehose escriba en S3 y en sus logs | Desplegado |
| `escritura-bronze-ventas` | Política inline del rol anterior | demo1 | Sobre el bucket: `s3:GetBucketLocation`, `ListBucket` y `ListBucketMultipartUploads`. Solo en `bronze/ventas/*` y `errors/ventas/*`: `AbortMultipartUpload`, `GetObject` y `PutObject`. Además, `logs:PutLogEvents` en el log group del stream | Desplegado |
| `api-ventas-firehose-put` | Política gestionada | demo1 | Solo `firehose:PutRecord` y `PutRecordBatch` sobre el ARN del stream. Sesión 1: se adjunta al usuario o rol del alumno si le faltan permisos. **Sesión 3: task role de ECS** | Desplegado |
| `dms-vpc-role` | Rol de cuenta (nombre fijo) + `AmazonDMSVPCManagementRole` | demo2 | DMS gestiona las ENI en la VPC | Destruido. Se recrea con `crear_roles_dms = true` |
| `dms-cloudwatch-logs-role` | Rol de cuenta (nombre fijo) + `AmazonDMSCloudWatchLogsRole` | demo2 | Logs de las tareas de DMS | Destruido |
| `curso-aws-hp-dms-secreto` | Rol (confianza: `dms.amazonaws.com` y `dms.eu-west-1.amazonaws.com`) con `leer-secreto-dms-user` | demo2 | DMS lee el secreto del usuario `dms_user` (`GetSecretValue`, `DescribeSecret`) | Destruido |
| `curso-aws-hp-dms-s3` | Rol con `escritura-bronze-cdc` | demo2 | DMS escribe en `bronze/cdc/*` (`PutObject`, `DeleteObject`, `PutObjectTagging`, `GetObject`; `ListBucket` y `GetBucketLocation` sobre el bucket) | Destruido |

En la base de datos (se destruyó con RDS): el usuario `dms_user` tiene `rds_replication`, `USAGE` y `SELECT` sobre `public`, y privilegios por defecto de `SELECT`. No es el usuario maestro (`retail_admin`).

---

## 8. Desviaciones respecto a HANDOFF.md

| Tema | HANDOFF.md | Real | Motivo |
|---|---|---|---|
| Clase de DMS | `dms.t3.micro` | `dms.t3.small` (variable `clase_dms`) | AWS ya no ofrece `dms.t3.micro` en ninguna región (`describe-orderable-replication-instances`, octubre de 2026). `dms.t3.small` cuesta 0,039 USD/h en eu-west-1 |
| Almacenamiento de DMS | No especificado | 50 GB | Incluidos en el precio de la instancia |
| PostgreSQL / DMS | «Versión soportada» y «versión estable más reciente» | PostgreSQL 17 (17.9 por defecto en RDS) y DMS 3.6.1 | DMS soporta PostgreSQL 17 y 18 como origen desde 3.5.4. 3.6.1 es la más reciente (3.5.4 sigue siendo la de por defecto) y se eligió 17 por estar más rodada |
| `ts_commit` | Columna de timestamp | **String** en Parquet | Comportamiento de DMS con `TimestampColumnName`; no es configurable. Las columnas de fecha propias sí van en `timestamp[ms]` |
| Formato de `event_ts` en bronze | El del contrato | El del contrato, gracias a `@field_serializer("event_ts", when_used="json")` en `Venta` | Sin él, Pydantic escribe microsegundos (`.481000Z`) |
| Cliente HTTP | (no especificado) | `httpx2` | La versión actual de Starlette lo pide para su `TestClient`. El generador también lo usa |
| Errores de AWS en la API | 503 solo con registros pendientes | También 503 ante `ClientError` o `BotoCoreError` (credenciales caducadas, stream inexistente) | Con un 500 el generador no reintenta y el error no se ve |
| `AWS_PROFILE` en el compose | `curso` fijo | `${AWS_PROFILE:-curso}` | Usar otro perfil sin editar el compose |
| Variables del generador en el compose | Valores fijos | `MODO`, `DURACION_MIN`, `DUPLICADOS_PCT` e `INVALIDOS_PCT` sustituibles desde el entorno; `TAM_LOTE` fijo a 25 | `MODO=pico docker compose up` |
| Generador como usuario 1000 | Solo pedido para la API | `USER 1000` también en el generador | Coherencia. En Linux, `salida/` debe ser escribible por el uid 1000 (README) |
| `REPLICA IDENTITY FULL` | No pedido | En `clientes` y `productos` | Para que el `D` llegue con la fila completa |
| `capture_ddls = false` en el endpoint de origen | No pedido | Activado | `dms_user` no es superusuario y no puede crear los objetos de captura de DDL |
| `backup_retention_period` de RDS | No pedido | 0 | Entorno efímero; acelera la creación |
| Log group de las tareas de DMS | «destroy elimina todo» | Queda `dms-tasks-curso-aws-hp-demo2` | Ver §6 |
| `CAMBIOS_DIAPOSITIVAS.md` | Debe existir | Borrado | Los cambios ya están aplicados en las diapositivas |
| Duración de la prueba de la demo 1 | 10 min en hora pico | 3 min en hora pico | Suficiente para validar los criterios. En clase se usan los 10 min por defecto |
| Perfil `curso` | Perfil de las pruebas | Se usó `default` (por variable y `AWS_PROFILE`) | La máquina de pruebas no tenía el perfil `curso`. Los valores por defecto del repositorio siguen siendo `curso` |
| SSO en Docker | Comprobar con `~/.aws/sso/cache` | **No probado** | El perfil de pruebas era de un usuario IAM con claves. La alternativa del `.env` está documentada |
| Athena y `.json.gz` | «Verifícalo» | Comprobada la extensión y el gzip real, **sin consulta en Athena** | Habría que crear una tabla en Glue (sesión 2) |

---

## 9. `comun/maestros.py`

Única fuente de tiendas, clientes y productos. Solo usa la biblioteca estándar. Es **determinista**: cada tabla tiene su propia semilla (`random.Random("2026-clientes")`, `"2026-productos"`), así que añadir campos a una no altera las otras. Un test compara la huella de los datos en dos procesos distintos. Las funciones devuelven tuplas de dataclasses inmutables cacheadas.

**API pública:**
- Datos: `tiendas()`, `tiendas_fisicas()`, `clientes()`, `productos()`.
- Índices: `indice_clientes()`, `indice_productos()`, `clientes_por_pais()`.
- Utilidades: `a_moneda_local(importe_eur, moneda)`, `decimales(moneda)`, `telefono_ficticio(n, pais)`, `nuevo_cliente(...)` y `como_dict(registro)`.

### Tiendas: 21 físicas + 5 online

Campos de `Tienda`: `tienda_id`, `nombre`, `pais`, `ciudad`, `formato` (`calle` | `centro comercial` | `outlet` | `online`) y `superficie_m2` (`None` online). Propiedades: `es_online`, `moneda` y `numero` (los 3 dígitos del `ticket_id`, `000` online).

| País | Moneda | Tiendas físicas |
|---|---|---|
| ES | EUR | ES-MAD-001, ES-MAD-002, ES-BCN-001, ES-VLC-001, ES-VLC-002, ES-VLC-003 |
| FR | EUR | FR-PAR-001, FR-PAR-002, FR-LYS-001, FR-MRS-001 |
| US | USD | US-NYC-001, US-NYC-002, US-LAX-001, US-CHI-001 |
| JP | JPY | JP-TYO-001, JP-TYO-002, JP-OSA-001, JP-KYO-001 |
| CN | CNY | CN-SHA-001, CN-PEK-001, CN-SZX-001 |

Canales online: `ONL-ES`, `ONL-FR`, `ONL-US`, `ONL-JP` y `ONL-CN`. Formatos: 10 de calle, 8 de centro comercial, 3 outlet y 5 online. En el generador cada canal online pesa como 4 tiendas físicas.

### Clientes: 4.000

Campos de `Cliente`: `cliente_id` (`C-1` … `C-4000`), `nombre`, `email` (`cliente<n>@ejemplo.com`), `telefono` (`+34 600 000 017`), `segmento`, `provincia`, `pais` y `fecha_alta` (entre 2018-01-01 y 2026-09-30).

- Segmento: Standard 3.202 y Premium 798 (~20 %).
- País: ES 1.569, FR 815, JP 612, US 603 y CN 401.
- Casos fijos:
  - **C-17:** Standard, Valencia, ES, alta el 2025-01-10. En RDS pasó a Premium en la demo 2.
  - **C-981:** Standard, Madrid, ES. Se borró en la demo 2.
  - **C-4001:** no existe en la semilla. Se insertó en la demo 2: Standard, Lyon, FR.

### Productos: 1.200 = 100 modelos × 3 colores × 4 tallas

Campos de `Producto`: `producto_id` (`P-<modelo>-<color>-<talla>`), `modelo` (`"0412"`), `color` (nombre: `Rojo`), `talla` (S, M, L, XL), `familia`, `temporada`, `precio_catalogo` (EUR, termina en `.95`) y `coste_unitario` (EUR, entre el 30 % y el 45 % del precio, por modelo).

- **Colores:** NEG Negro, BLA Blanco, AZU Azul, ROJ Rojo, BEI Beige, VER Verde y GRI Gris.
- **Modelos por familia:** punto 21, calzado 16, pantalones 14, abrigos 11, accesorios 11, vestidos 10, camisas 9 y baño 8.
- **Temporadas:** PV26 612 y OI26 588. Abrigos y punto siempre en OI26; baño siempre en PV26.
- **Precios:** de 17,95 a 196,95 EUR.
- **Caso fijo:** `P-0412-ROJ-M`, un vestido PV26 de 39,95 EUR con coste de 15,74.

### Tipos de cambio (ilustrativos y fijos; 1 EUR = …)

USD 1,08 · JPY 160 · CNY 7,8. Se redondea a 2 decimales y JPY a 0. Ejemplo: 39,95 EUR = 43,15 USD = 6.392 JPY = 311,61 CNY.

---

## 10. Versiones fijadas y tests

| Componente | Versión |
|---|---|
| Terraform | `required_version = ">= 1.6"`. Probado con 1.15.3 |
| Proveedor `hashicorp/aws` | `~> 6.70`. Lock: 6.70.0 en los tres módulos |
| Proveedor `hashicorp/random` | `~> 3.9`. Lock: 3.9.1 (demo2) |
| Proveedor `hashicorp/http` | `~> 3.6`. Lock: 3.6.3 (demo2) |
| Python | 3.12. Imágenes `python:3.12-slim`; entorno local 3.12.13 |
| API (`demo1-ingesta/api/requirements.txt`) | fastapi 0.162.0, uvicorn 0.54.0, boto3 1.43.120 |
| Generador (`demo1-ingesta/generador/requirements.txt`) | httpx2 2.16.0 |
| Scripts (`requirements.txt`) | boto3 1.43.120, psycopg[binary] 3.3.6, pyarrow 26.0.0 |
| Desarrollo (`requirements-dev.txt`) | Lo anterior + pytest 9.2.0, moto[firehose,s3] 5.2.5 y ruff 0.17.3 |
| RDS / DMS | PostgreSQL 17 (17.9) / motor 3.6.1 |
| Moto server (prueba local, no está en el repositorio) | `motoserver/moto:5.2.5` |

**Tests y validación** (desde la raíz):

```bash
pip install -r requirements-dev.txt
pytest                          # 27 tests, ~5 s, sin AWS
ruff check .
terraform fmt -check -recursive
(cd infra/base && terraform init -backend=false && terraform validate)   # ídem en los otros dos módulos
```

- **`pytest` sin opciones.** Lo configura `pyproject.toml`: `--import-mode=importlib`, `pythonpath` con la raíz, `demo1-ingesta/api` y `demo1-ingesta/generador`, y `testpaths` en las dos carpetas de tests.
- **Qué cubren:**
  - **API:** 14 tests con `botocore.stub.Stubber`. Validación, 422 por lote, reintentos de los fallidos, 503 y formato de `event_ts`.
  - **Maestros:** 6 tests. Casos fijos y determinismo entre procesos.
  - **Generador:** 7 tests. Contrato del evento, validación contra `Venta`, reglas de los tickets, configuración y una prueba de extremo a extremo (generador → API → Firehose y S3 simulados con moto) que cuadra los recuentos con el resumen, con duplicados e inválidos.
- **`ruff`:** `select = E, F, W, I, B, UP` e `ignore = B905`, porque el `zip()` sin `strict=` está así en el código de las diapositivas. No se aplica `ruff format`, que reformatearía ese código.
