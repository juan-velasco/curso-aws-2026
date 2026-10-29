# Handoff: código de las demos de la sesión 1 · Curso AWS para HP

> **Para el profesor.** Abre Claude Code en una carpeta vacía (será la raíz del repositorio), copia este fichero como `HANDOFF.md` y pídele: *«Lee HANDOFF.md y construye el repositorio siguiendo el plan de trabajo. Pregúntame antes de cualquier acción que cree, modifique o borre recursos en AWS»*. Usa una cuenta de AWS de pruebas, no la de producción.

---

## 1. Contexto

Este repositorio contiene el código de las dos demos de la **sesión 1** de un curso de AWS de 12 horas (3 sesiones) que imparte el Instituto Tecnológico de Informática (ITI) para el cliente HP. El hilo conductor es un **retail de moda global** cuyas ventas alimentan un lago de datos en AWS con arquitectura medallón (bronze, silver, gold).

La sesión 1 cubre la **ingesta hacia la capa bronze** por dos vías:

| Demo | Qué enseña | Flujo |
|---|---|---|
| **Demo 1 · Del TPV a bronze** | Ingesta en streaming de los hechos (ventas) | Generador → API REST (FastAPI en Docker) → Amazon Data Firehose → S3 `bronze/ventas/` |
| **Demo 2 · CDC con DMS** | Captura de cambios de las dimensiones (clientes, productos) | RDS PostgreSQL → AWS DMS (Full load + CDC) → S3 `bronze/cdc/` |

El código de las diapositivas ya está escrito y los alumnos lo verán proyectado: **el repositorio debe respetarlo** salvo donde este documento indica lo contrario. Las sesiones 2 y 3 reutilizan este repositorio (Glue, Redshift, ECS con Fargate, SageMaker), así que los nombres, los datos y los contratos que se fijan aquí son definitivos.

Los ejercicios A y B de la sesión 1 son de papel y **no necesitan código**.

### Restricciones generales

- **Coste mínimo.** Cada alumno usa su propia cuenta. Nada debe quedar encendido con coste por hora salvo durante la demo 2, que se destruye al terminar.
- **Multiplataforma.** Los alumnos usan Windows, macOS o Linux con Docker Desktop, Python 3.12, Terraform, AWS CLI v2 y VS Code. Los scripts de apoyo se escriben **en Python**, no en bash, para que funcionen igual en los tres sistemas. Donde la documentación muestre comandos, dar la versión de bash y la de PowerShell si difieren.
- **Idioma.** README, comentarios, mensajes de log y nombres de dominio en español (como en las diapositivas). Identificadores técnicos de AWS, en su forma original.
- **Sin secretos en el repositorio.** `.gitignore` con `.env`, `*.tfstate*`, `.terraform/`, `__pycache__/`, `salida/`.

---

## 2. Decisiones ya tomadas

| Tema | Decisión |
|---|---|
| Región | `eu-west-1` (Irlanda), configurable por variable |
| Perfil de AWS CLI | `curso` |
| Bucket del lago | `retail-company-datalake-prod-<sufijo>`. Los nombres de bucket son únicos en todo AWS: el sufijo por defecto es el ID de cuenta (`data.aws_caller_identity`). En las diapositivas aparece sin sufijo, como ejemplo |
| Stream de Firehose | `hp-retail-ventas` |
| Buffer de Firehose | **30 s o 5 MiB** (el primero que se cumpla), compresión GZIP |
| Prefijo de bronze | `bronze/ventas/anio=!{timestamp:yyyy}/mes=!{timestamp:MM}/dia=!{timestamp:dd}/` (fecha de **llegada**, no de negocio) |
| Prefijo de errores | `errors/ventas/!{firehose:error-output-type}/!{timestamp:yyyy/MM/dd}/` |
| Ruta de DMS | Un único target endpoint con carpeta `bronze/cdc` → `bronze/cdc/public/clientes/` y `bronze/cdc/public/productos/` |
| Formato de DMS | Parquet, con columna de timestamp de commit `ts_commit` y carpetas por fecha `AAAA/MM/DD` para los ficheros CDC |
| Segmentos de cliente | `Standard` y `Premium` (en inglés, siempre con mayúscula inicial) |
| Etiquetas | Todos los recursos con `proyecto = curso-aws-hp`, `sesion = 1` y `demo = base \| demo1 \| demo2` |
| Estado de Terraform | Local, uno por módulo. Sin backend remoto |

---

## 3. Estructura del repositorio

```
curso-aws-hp/
├── README.md                     # visión general, requisitos, orden de ejecución
├── HANDOFF.md                    # este documento
├── .gitignore
├── comun/
│   └── maestros.py               # datos maestros deterministas (tiendas, clientes, productos)
├── infra/
│   └── base/                     # Terraform: bucket del lago + AWS Budgets (se mantiene entre sesiones)
├── demo1-ingesta/
│   ├── infra/                    # Terraform: Firehose, IAM, alarma
│   ├── api/                      # FastAPI + Dockerfile + requirements.txt + tests
│   ├── generador/                # generador de ventas + Dockerfile + tests
│   ├── docker-compose.yml
│   ├── scripts/                  # comprobar_bronze.py, evento_invalido.py
│   └── GUION.md                  # guion de la demo para el profesor
├── demo2-cdc-dms/
│   ├── infra/                    # Terraform: VPC, RDS, Secrets Manager, DMS
│   ├── sql/                      # esquema, usuario DMS, cambios de la demo
│   ├── scripts/                  # cargar_semilla.py, tarea_dms.py, comprobar_cdc.py
│   └── GUION.md
└── CAMBIOS_DIAPOSITIVAS.md       # lo que haya que ajustar en las diapositivas (ver §9)
```

`comun/maestros.py` es la **única fuente** de tiendas, clientes y productos. Lo usan el generador (demo 1) y la carga de la base de datos (demo 2), de modo que un `cliente_id` o un `producto_id` de una venta siempre existe en los maestros replicados por DMS. Como el generador corre en Docker, el `Dockerfile` del generador debe copiar `comun/` (usar `context: ..` en el compose o un paquete instalable; elige lo más sencillo).

---

## 4. Datos maestros (`comun/maestros.py`)

Generación **determinista** (semilla fija, p. ej. `random.Random(2026)`): dos ejecuciones producen exactamente los mismos datos. Sin dependencias externas.

### Países, tiendas y monedas

Cinco países, 21 tiendas físicas y un canal online por país. Los países y monedas deben ser estos porque las sesiones 2 y 3 los usan (filtro de Lake Formation para Asia, reglas de calidad sobre la moneda, dashboard con España, Japón y Francia).

| País | Moneda | Tiendas | Ejemplos de `tienda_id` |
|---|---|---|---|
| ES | EUR | 6 | `ES-VLC-003`, `ES-MAD-001`, `ES-BCN-001`… |
| FR | EUR | 4 | `FR-PAR-001`, `FR-LYS-001`… |
| US | USD | 4 | `US-NYC-001`… |
| JP | JPY | 4 | `JP-TYO-001`… |
| CN | CNY | 3 | `CN-SHA-001`… |

- Formato: `<PAÍS>-<CIUDAD, 3 letras>-<NNN>`. **`ES-VLC-003` debe existir** (aparece en el contrato del evento de las diapositivas).
- Canal online: `tienda_id = "ONL-<PAÍS>"` (p. ej. `ONL-ES`), con `canal` `WEB` o `APP`.
- Atributos de tienda: `tienda_id`, `nombre`, `pais`, `ciudad`, `formato` (calle, centro comercial, outlet, online), `superficie_m2`.

### Clientes (4.000)

- `cliente_id`: `C-1` … `C-4000`, **sin ceros a la izquierda**.
- Atributos: `cliente_id`, `nombre`, `email`, `telefono`, `segmento` (`Standard` ~80 %, `Premium` ~20 %), `provincia` (ciudad o región), `pais`, `fecha_alta`.
- Casos fijos que usan las diapositivas:
  - **C-17**: `Standard`, provincia `Valencia`, país ES, `fecha_alta` 2025-01-10.
  - **C-981**: `Standard`, provincia `Madrid`, país ES (se borra en la demo 2).
  - **C-4001 no existe** en la semilla (se inserta en la demo 2: `Standard`, `Lyon`, FR).
- Datos personales ficticios y evidentes (p. ej. `cliente17@ejemplo.com`, teléfonos `+34 600 000 017`).

### Productos (1.200)

- 100 modelos × 3 colores × 4 tallas = 1.200 referencias.
- `producto_id`: `P-<modelo, 4 dígitos>-<COLOR, 3 letras>-<TALLA>`. **`P-0412-ROJ-M` debe existir**.
- Colores (códigos y nombres): NEG Negro, BLA Blanco, AZU Azul, ROJ Rojo, BEI Beige, VER Verde, GRI Gris.
- Tallas: S, M, L, XL.
- Familias: vestidos, camisas, pantalones, abrigos, punto, baño, calzado, accesorios.
- Temporada: `PV26` (primavera-verano) u `OI26` (otoño-invierno), coherente con la familia (abrigos y punto en OI, baño en PV).
- Atributos: `producto_id`, `modelo`, `color`, `talla`, `familia`, `temporada`, `precio_catalogo` (EUR), `coste_unitario` (EUR, entre el 30 % y el 45 % del precio).

### Tipos de cambio ilustrativos

Para convertir el precio de catálogo (EUR) a la moneda local: USD 1,08 · JPY 160 · CNY 7,8. Redondear a 2 decimales (JPY sin decimales). Son valores fijos y así debe indicarse en un comentario.

---

## 5. Demo 1 · Del TPV a bronze

### 5.1 Infraestructura base (`infra/base/`)

Se crea una vez y se mantiene para las sesiones 2 y 3.

- **Bucket** `retail-company-datalake-prod-<sufijo>`:
  - Bloqueo de acceso público, cifrado SSE-S3, versionado activado.
  - `force_destroy = true` (es un entorno de curso; documentarlo en el README).
  - Lifecycle sobre `bronze/`: Standard-IA a 30 días, Glacier Instant Retrieval a 90, Glacier Deep Archive a 365. Expirar versiones no actuales a los 30 días.
  - Lifecycle sobre `athena-results/`: expirar a los 7 días (lo usa la sesión 2).
- **AWS Budgets**: presupuesto mensual de **10 USD** con aviso por email al 80 % y al 100 % (variable `email_alertas`).
- Outputs: `bucket_name`, `bucket_arn`, `region`, `account_id`.

### 5.2 Infraestructura de la demo 1 (`demo1-ingesta/infra/`)

Lee el bucket de `infra/base` (por variable o `terraform_remote_state` con backend local; elige lo más simple de explicar).

- **Firehose** `hp-retail-ventas`: Direct PUT → S3 (`extended_s3`).
  - Buffer 30 s / 5 MiB, compresión GZIP.
  - Prefijos de bronze y de errores de la §2.
  - **Extensión de fichero `.json.gz`** (parámetro de extensión personalizada). Athena decide la descompresión por la extensión: sin `.gz` no lee los ficheros en la sesión 2. Verifícalo.
  - Sin transformación con Lambda, sin conversión de formato, sin particionado dinámico (las diapositivas lo explican, pero bronze queda como copia fiel).
  - Logs de errores de entrega en CloudWatch Logs.
- **Rol IAM de Firehose** con permisos mínimos sobre el bucket (prefijos `bronze/ventas/` y `errors/ventas/`) y CloudWatch Logs.
- **Política gestionada `api-ventas-firehose-put`**: solo `firehose:PutRecord` y `firehose:PutRecordBatch` sobre el ARN del stream. En la sesión 1 el alumno puede adjuntarla a su usuario o rol si su perfil no tiene permisos; en la sesión 3 la usará el task role de ECS.
- **Alarma de CloudWatch** sobre `DeliveryToS3.DataFreshness` > 120 s, con un tema SNS opcional (variable `email_alertas`; la suscripción hay que confirmarla por email).
- Outputs: `stream_name`, `stream_arn`, `bucket_name`.

### 5.3 API de ventas (`demo1-ingesta/api/`)

Parte del **código de las diapositivas** (reproducido en el anexo A) y mantenlo lo más parecido posible. Cambios necesarios:

1. **Tamaño del lote.** La diapositiva hace `lote[:500]`, lo que descarta en silencio lo que pase de 500. Valida en su lugar el tamaño máximo con Pydantic (`Annotated[list[Venta], Field(min_length=1, max_length=500)]`): si llegan más, 422. Anótalo en `CAMBIOS_DIAPOSITIVAS.md`.
2. **Fallo definitivo de envío.** Si tras los reintentos quedan registros sin enviar, responder **503** con el número de registros pendientes, en vez de un 500 genérico.
3. **Logs.** Una línea por lote recibido (registros, enviados, reintentos), en formato legible.
4. **Región.** Leer `AWS_REGION` o `AWS_DEFAULT_REGION`; si no hay ninguna, fallar al arrancar con un mensaje claro.

Endpoints: `POST /ventas/lote` (202 con `{"enviados": n}`), `GET /health`, `GET /docs` (lo genera FastAPI).

**Dockerfile**: `python:3.12-slim`, dependencias con versiones fijadas en `requirements.txt` (fastapi, uvicorn, boto3; usa las últimas estables y fíjalas), `USER 1000`, `uvicorn` en el puerto 8000. Variable `HOME` apuntando a un directorio escribible para el usuario 1000.

**Tests (`api/tests/`, pytest)**, sin AWS. Simula Firehose con `botocore.stub.Stubber` o `moto`. Casos:

- Evento válido → 202.
- `event_id` que no es UUID, `unidades = 0`, `precio_unitario` negativo, `moneda` de 2 letras → 422.
- Más de 500 registros → 422.
- `FailedPutCount > 0` en el primer intento → se reintentan **solo** los fallidos y se responde 202.
- Fallos persistentes → 503.

### 5.4 Generador (`demo1-ingesta/generador/`)

Envía lotes de ventas a la API. Usa `comun/maestros.py`.

**Contrato del evento** (no cambiar nombres ni tipos; es el de las diapositivas):

```json
{
  "event_id": "7f3c2a9e-5b1d-4c8e-9a0f-2d6e8b1c4a77",
  "event_ts": "2026-10-24T10:15:32.481Z",
  "canal": "TPV",
  "tienda_id": "ES-VLC-003",
  "ticket_id": "T-20261024-003-000187",
  "linea": 2,
  "cliente_id": "C-17",
  "producto_id": "P-0412-ROJ-M",
  "unidades": 1,
  "precio_unitario": 39.95,
  "descuento": 8.00,
  "moneda": "EUR",
  "medio_pago": "TARJETA"
}
```

Reglas de generación:

- **Un evento = una línea de ticket.** Cada ticket tiene de 1 a 4 líneas con el mismo `ticket_id` y `linea` correlativa desde 1.
- `ticket_id`: `T-<AAAAMMDD>-<número de tienda, 3 dígitos>-<secuencia, 6 dígitos>`. Para el canal online, usar `000` como número de tienda.
- `event_ts`: hora actual en UTC con milisegundos y sufijo `Z`. Todas las líneas de un ticket comparten `event_ts`.
- `canal`: `TPV` en tiendas físicas; `WEB` o `APP` en el canal online.
- `cliente_id`: nulo en ~30 % de los tickets (cliente sin tarjeta).
- `precio_unitario`: precio de catálogo convertido a la moneda del país.
- `descuento`: 0 en la mayoría de líneas; entre el 10 % y el 30 % del importe en algunas. Nunca mayor que el importe de la línea.
- `medio_pago`: `TARJETA`, `EFECTIVO` o `MOVIL` en tienda; `TARJETA` o `PAYPAL` online.
- `unidades`: 1 casi siempre, 2 o 3 de vez en cuando.

**Configuración por variables de entorno** (con los valores por defecto de las diapositivas):

| Variable | Defecto | Uso |
|---|---|---|
| `API_URL` | `http://api:8000` | En la sesión 3 apuntará a la IP de la tarea de Fargate |
| `EVENTOS_POR_SEGUNDO` | `1` | Ritmo base |
| `MODO` | `normal` | `pico` multiplica el ritmo por 10 (las diapositivas hablan de «hora pico» y de picos de 10 eventos/s) |
| `DURACION_MIN` | `10` | Duración de la ejecución |
| `TAM_LOTE` | `25` | Máximo de eventos por petición; se envía también al pasar 1 s |
| `DUPLICADOS_PCT` | `0` | Porcentaje de eventos que se reenvían con el mismo `event_id` (la sesión 2 los usa para enseñar a desduplicar) |
| `INVALIDOS_PCT` | `0` | Porcentaje de eventos inválidos enviados en peticiones aparte; se espera un 422 |

- Reintenta ante errores de red o 5xx de la API con backoff.
- Al terminar, escribe `salida/resumen.json` (montado como volumen) con: eventos enviados, aceptados, duplicados enviados, inválidos rechazados, hora de inicio y fin. Lo usa el script de comprobación.
- Muestra el progreso en el log cada 10 s.

**Tests**: maestros deterministas (21 tiendas, 4.000 clientes, 1.200 productos, C-17 Standard en Valencia, existen `ES-VLC-003` y `P-0412-ROJ-M`, no existe C-4001). Además, cada evento generado valida contra el modelo `Venta` de la API.

### 5.5 docker-compose (`demo1-ingesta/docker-compose.yml`)

Parte del compose de las diapositivas (anexo A), con estos añadidos imprescindibles:

```yaml
    environment:
      FIREHOSE_STREAM: hp-retail-ventas
      AWS_PROFILE: curso
      AWS_REGION: eu-west-1                       # sin región, boto3 no crea el cliente
      AWS_SHARED_CREDENTIALS_FILE: /aws/credentials
      AWS_CONFIG_FILE: /aws/config                # necesario para perfiles con SSO o región
```

- El generador espera a que la API esté sana (`depends_on` con `condition: service_healthy` y healthcheck sobre `/health`).
- Volumen `./salida` para el resumen del generador.
- **Linux con un usuario distinto de 1000**: el contenedor no podrá leer `~/.aws`. Documenta la alternativa en el README: generar un `.env` con `aws configure export-credentials --profile curso --format env-no-export` y usar `env_file`. Las credenciales temporales caducan; el `.env` no se sube a git.
- Si el perfil `curso` usa IAM Identity Center (SSO), el token se lee de `~/.aws/sso/cache`; comprueba que funciona con el montaje de solo lectura y, si no, documenta la alternativa del `.env`.

### 5.6 Scripts de apoyo (`demo1-ingesta/scripts/`)

- **`comprobar_bronze.py`**: comprueba la ejecución en S3.
  - Lista los objetos de bronze de la fecha actual (o la indicada con `--fecha`).
  - Descarga y descomprime los ficheros, y cuenta líneas y `event_id` distintos.
  - Compara el resultado con `salida/resumen.json`.
  - Lista lo que haya en `errors/ventas/`.
  - Muestra el último valor de `DataFreshness`.
  - Termina con un resumen OK/KO de cada criterio de aceptación.
- **`evento_invalido.py`**: envía a la API un evento inválido y muestra el detalle del 422, como hace el `curl` de las diapositivas.

### 5.7 Criterios de aceptación (de la diapositiva «Qué comprobar»)

- [ ] Estructura `bronze/ventas/anio=AAAA/mes=MM/dia=DD/` con ficheros `.json.gz` en JSON Lines.
- [ ] Con buffer de 30 s, aparece un fichero nuevo aproximadamente cada 30 segundos mientras el generador está activo.
- [ ] Nº de líneas en bronze = eventos aceptados por la API (con `DUPLICADOS_PCT=0`).
- [ ] `DataFreshness` por debajo de 2 minutos.
- [ ] Nada en `errors/` salvo pruebas provocadas.
- [ ] El evento inválido devuelve 422 con el campo que falla.
- [ ] Los comandos de la diapositiva «Demo 1: comandos» (anexo A) funcionan tal cual o con los mínimos cambios, que se anotan en `CAMBIOS_DIAPOSITIVAS.md`.

---

## 6. Demo 2 · CDC de clientes con DMS

Este módulo **cobra por hora** (RDS y la instancia de replicación): se crea para la demo y se destruye al terminar.

### 6.1 Infraestructura (`demo2-cdc-dms/infra/`)

- **Red propia y mínima**:
  - VPC con dos subredes públicas en dos zonas de disponibilidad (DMS y RDS exigen dos zonas en sus subnet groups) e internet gateway.
  - **Sin NAT Gateway ni endpoints de interfaz**, porque cobran por hora. Endpoint de gateway para S3 (gratuito).
- **RDS PostgreSQL**:
  - `db.t4g.micro`, 20 GB gp3, single-AZ, `skip_final_snapshot = true`, `deletion_protection = false`.
  - Versión mayor **soportada como origen por la versión de DMS elegida**. Comprueba la compatibilidad en la documentación de DMS.
  - Parameter group con `rds.logical_replication = 1` (y `wal_sender_timeout = 0`, como recomienda DMS). Verifica tras crear la instancia que `SHOW wal_level` devuelve `logical`; si no, reinicia la instancia.
  - `publicly_accessible = true` con security group que solo admite el puerto 5432 desde la IP del alumno (variable `mi_ip`, o detección automática) y desde el security group de DMS. Así se carga la semilla desde el portátil sin bastión.
- **Credenciales**:
  - Contraseña maestra con `random_password`. Queda en el estado local de Terraform; documéntalo y no subas el estado a git.
  - Secreto en Secrets Manager para el usuario de DMS, con las claves que espera DMS para PostgreSQL (`username`, `password`, `host`, `port`).
  - Rol IAM que permite a DMS leer ese secreto.
- **Roles de cuenta de DMS**: `dms-vpc-role` (política `AmazonDMSVPCManagementRole`) y `dms-cloudwatch-logs-role` (`AmazonDMSCloudWatchLogsRole`).
  - DMS los necesita con esos nombres exactos y **pueden existir ya** en una cuenta de empresa. Variable `crear_roles_dms` (por defecto `true`) para no crearlos si ya están.
  - El subnet group de DMS debe depender de que el rol exista.
- **Instancia de replicación**: `dms.t3.micro`, versión de motor estable más reciente, `publicly_accessible = true` (para llegar a Secrets Manager sin endpoints de pago).
- **Source endpoint**: PostgreSQL con el secreto, SSL requerido.
- **Target endpoint S3** (`aws_dms_s3_endpoint`):
  - Bucket de `infra/base` con carpeta `bronze/cdc`.
  - Formato Parquet, timestamps en milisegundos (compatibilidad con Athena), columna de timestamp `ts_commit`.
  - Particionado por fecha activado con secuencia `YYYYMMDD` y separador `/`.
  - Intervalo máximo de lote CDC de 60 s, para que los cambios aparezcan rápido en la demo.
  - Rol de acceso a S3 limitado al prefijo `bronze/cdc/`.
  - Sin `Op` en la carga completa (comportamiento por defecto): las diapositivas dicen que la carga inicial no lleva `Op`.
- **Tarea de replicación**: `full-load-and-cdc`, reglas de selección para `public.clientes` y `public.productos`, logging en CloudWatch activado y **sin arranque automático** (se arranca en la demo con un script).
- Outputs: endpoint de RDS, ARN de la tarea, nombre del secreto, comando para conectarse con `psql`.

### 6.2 Base de datos (`demo2-cdc-dms/sql/`)

- **`01_esquema.sql`**:
  - Tabla `clientes` (`cliente_id` PK, `nombre`, `email`, `telefono`, `segmento` con CHECK en `Standard`/`Premium`, `provincia`, `pais`, `fecha_alta`, `actualizado_en`).
  - Tabla `productos` (`producto_id` PK, `modelo`, `color`, `talla`, `familia`, `temporada`, `precio_catalogo`, `coste_unitario`).
  - Las claves primarias son imprescindibles para que DMS replique bien los UPDATE y DELETE.
- **`02_usuario_dms.sql`**: usuario `dms_user` con el rol `rds_replication` y SELECT sobre el esquema `public`. La diapositiva de pasos dice «crear un usuario con permisos de replicación»: no usar el usuario maestro.
- **`03_cambios_demo.sql`**: los cambios que muestra la diapositiva «Qué deja DMS en bronze»:
  - `UPDATE` de **C-17** a `Premium`.
  - `INSERT` de **C-4001** (`Standard`, `Lyon`, FR).
  - `DELETE` de **C-981**.

### 6.3 Scripts (`demo2-cdc-dms/scripts/`)

Todos en Python (psycopg y boto3) y leyendo los outputs de Terraform.

- **`cargar_semilla.py`**:
  - Crea el esquema y el usuario de DMS.
  - Carga los 4.000 clientes y 1.200 productos de `comun/maestros.py`.
  - Es idempotente: si ya hay datos, avisa y no duplica.
- **`tarea_dms.py`**: con los subcomandos `probar` (test de conexión de ambos endpoints), `iniciar`, `estado` y `parar`.
- **`aplicar_cambios.py`**: ejecuta `03_cambios_demo.sql`.
- **`comprobar_cdc.py`**:
  - Lista los ficheros de `bronze/cdc/public/clientes/`.
  - Cuenta las filas del fichero LOAD.
  - Localiza los ficheros CDC y muestra sus filas, con `Op`, `cliente_id`, `segmento`, `provincia` y `ts_commit`, como en la diapositiva.
  - Usa pyarrow o pandas.

### 6.4 Criterios de aceptación

- [ ] `SHOW wal_level` = `logical` en RDS.
- [ ] El test de conexión de los dos endpoints es correcto.
- [ ] Fichero LOAD de clientes con **4.000 filas** y de productos con **1.200**, sin columna `Op`.
- [ ] Tras `aplicar_cambios.py`, en menos de 2 minutos aparece un fichero CDC en `…/AAAA/MM/DD/` con tres filas: `U` de C-17 (`Premium`), `I` de C-4001 y `D` de C-981, cada una con `ts_commit`.
- [ ] `tarea_dms.py parar` deja la tarea en `stopped` y `terraform destroy` elimina todo sin intervención manual.

---

## 7. Guiones de las demos (`GUION.md` en cada carpeta)

Una página por demo para el profesor, con los pasos de la diapositiva correspondiente, el comando exacto de cada paso (bash y PowerShell si difieren), la salida esperada y qué hacer si algo falla. Pasos de las diapositivas:

**Demo 1**

1. Crear la infraestructura base con Terraform: bucket, stream de Firehose y rol IAM.
2. Levantar API y generador con `docker compose up --build`.
3. Generar 10 minutos de ventas en hora pico.
4. Seguir las métricas del stream en CloudWatch.
5. Explorar bronze en S3: un fichero gzip cada 30 s con JSON Lines.
6. Enviar un evento inválido y ver el 422 de la API.

**Demo 2**

1. RDS PostgreSQL db.t4g.micro con `rds.logical_replication = 1`.
2. Script de semilla: 4.000 clientes y 1.200 productos.
3. Crear los endpoints con el secreto en Secrets Manager y probar la conexión.
4. Tarea Full load + CDC hacia bronze en Parquet.
5. UPDATE del segmento de C-17 y localizar el fichero CDC en S3.
6. Parar la tarea y la instancia de replicación al terminar.

Incluir en cada guion el **tiempo aproximado** de cada paso (la creación de RDS y de la instancia de DMS tarda varios minutos: indicar que conviene lanzarla antes de empezar la explicación) y un apartado de **limpieza** que coincida con el checklist de la diapositiva:

- Firehose y bucket se mantienen.
- La tarea de DMS se para y la instancia de replicación se borra.
- RDS se detiene o, mejor, se destruye con el módulo (AWS reinicia una RDS detenida a los 7 días).
- `docker compose down`.

---

## 8. Plan de trabajo y reglas para Claude Code

### Reglas

- **Pregunta antes** de cualquier `terraform apply`, `terraform destroy` o comando que cree, modifique o borre recursos en AWS. Antes de cada `apply`, muestra un resumen del plan (recursos y si alguno tiene coste por hora).
- No toques recursos que no haya creado este repositorio. Si un nombre ya existe (p. ej. los roles de DMS), detente y pregunta.
- Tras probar la demo 2, **propón destruir** su módulo.
- Fija versiones: Terraform `>= 1.6`, proveedor AWS en la última versión mayor estable (compruébala), dependencias de Python fijadas en `requirements.txt`.
- Formatea y valida: `terraform fmt`, `terraform validate`, `ruff` (o similar) y `pytest` deben pasar antes de dar algo por terminado.

### Orden

1. Estructura del repositorio, `.gitignore`, `comun/maestros.py` y sus tests.
2. API con tests locales (sin AWS).
3. Generador con tests locales; prueba API + generador con Firehose simulado.
4. `infra/base` y `demo1-ingesta/infra`: `fmt`, `validate`, `plan` → **preguntar** → `apply`.
5. Demo 1 completa contra AWS y `comprobar_bronze.py` en verde.
6. `demo2-cdc-dms/infra`: `plan` → **preguntar** → `apply`; semilla, tarea, cambios y `comprobar_cdc.py` en verde.
7. Guiones, README y `CAMBIOS_DIAPOSITIVAS.md`.
8. Proponer `destroy` de la demo 2 (la base y la demo 1 se mantienen para la sesión 2).

---

## 9. Cambios en las diapositivas (`CAMBIOS_DIAPOSITIVAS.md`)

Crea este fichero con una tabla `diapositiva | texto actual | texto propuesto | motivo`. Incluye al menos lo que ya se sabe y añade lo que surja al probar:

| Diapositiva (sesión 1) | Cambio |
|---|---|
| Demo 1: del TPV a la capa bronze | «un fichero gzip por minuto» → «un fichero gzip cada 30 s» (buffer de 30 s) |
| Dockerizar la API y el generador | Añadir `AWS_REGION` y `AWS_CONFIG_FILE` al compose |
| La API: envío a Firehose con reintentos | `lote[:500]` → validación de tamaño máximo con 422 |
| Amazon S3 como base del lago | Nombre real de los ficheros (`hp-retail-ventas-1-…json.gz`) y nota sobre el sufijo del bucket |
| Qué deja DMS en bronze | `bronze/clientes/public/clientes/` → `bronze/cdc/public/clientes/` |
| Arquitectura de una tarea de DMS | «bronze/clientes/ y bronze/productos/» → «bronze/cdc/public/…» |
| Amazon S3 como base del lago (árbol) | Sustituir `clientes/` y `productos/` por `cdc/public/clientes/` y `cdc/public/productos/` |

Y en la **sesión 2** (para que el profesor lo tenga en cuenta): las diapositivas «Crawlers: configuración y buenas prácticas» y «Demo 2: catálogo y Athena sobre bronze» citan `bronze/clientes/` y `bronze/productos/`; pasan a `bronze/cdc/public/clientes/` y `bronze/cdc/public/productos/`.

---

## 10. Fuera de alcance

- Glue, Athena, Redshift, Step Functions, Lake Formation y QuickSight (sesión 2).
- Despliegue en ECS con Fargate, Cognito, GuardDuty, Inspector y SageMaker (sesión 3). Pero el código debe permitirlo sin cambios: imagen de la API sin credenciales dentro, región y stream por variables de entorno, `API_URL` configurable en el generador y la política `api-ventas-firehose-put` reutilizable.
- El histórico sintético para Machine Learning (sesión 3). Diseña `comun/maestros.py` para que se pueda reutilizar en esa generación.

---

## Anexo A · Código tal como aparece en las diapositivas

**Modelo y cliente** (diapositiva «La API: modelo del evento con Pydantic»):

```python
import json, os, time
from datetime import datetime
from uuid import UUID
import boto3
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="API de ventas")
fh = boto3.client("firehose")
STREAM = os.environ["FIREHOSE_STREAM"]

class Venta(BaseModel):
    event_id: UUID
    event_ts: datetime
    canal: str
    tienda_id: str
    ticket_id: str
    linea: int = Field(ge=1)
    cliente_id: str | None = None
    producto_id: str
    unidades: int = Field(ge=1)
    precio_unitario: float = Field(gt=0)
    descuento: float = Field(ge=0)
    moneda: str = Field(min_length=3, max_length=3)
    medio_pago: str
```

**Envío con reintentos** (diapositiva «La API: envío a Firehose con reintentos»):

```python
def enviar(ventas: list[Venta]) -> int:
    records = [{"Data": (v.model_dump_json() + "\n").encode()}
               for v in ventas]
    for intento in range(5):
        resp = fh.put_record_batch(
            DeliveryStreamName=STREAM, Records=records)
        if resp["FailedPutCount"] == 0:
            return len(ventas)
        # reintentar solo los registros que fallaron
        records = [r for r, res in
                   zip(records, resp["RequestResponses"])
                   if "ErrorCode" in res]
        time.sleep(0.2 * 2 ** intento)
    raise RuntimeError(f"{len(records)} registros sin enviar")

@app.post("/ventas/lote", status_code=202)
def recibir(lote: list[Venta]):
    return {"enviados": enviar(lote[:500])}

@app.get("/health")
def health():
    return {"status": "ok"}
```

**Dockerfile y compose** (diapositiva «Dockerizar la API y el generador»):

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app
USER 1000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      FIREHOSE_STREAM: hp-retail-ventas
      AWS_PROFILE: curso
      AWS_SHARED_CREDENTIALS_FILE: /aws/credentials
    volumes: ["~/.aws:/aws:ro"]
  generador:
    build: ./generador
    environment:
      API_URL: http://api:8000
      EVENTOS_POR_SEGUNDO: "1"
      DURACION_MIN: "10"
```

**Comandos de la demo 1** (diapositiva «Demo 1: comandos»):

```bash
# 1. Infraestructura base (bucket, stream de Firehose, rol IAM)
cd infra/sesion1 && terraform init && terraform apply

# 2. API + generador en local
docker compose up --build -d
docker compose logs -f generador

# 3. ¿Qué ha llegado a bronze?
aws s3 ls s3://$BUCKET/bronze/ventas/ --recursive | tail -5
aws s3 cp s3://$BUCKET/bronze/ventas/anio=2026/mes=10/dia=24/$FICHERO - \
  | gunzip | head -3 | jq .

# 4. Probar la validación del contrato
curl -s -X POST localhost:8000/ventas/lote \
  -H 'Content-Type: application/json' \
  -d '[{"event_id": "no-es-uuid"}]' | jq '.detail[0]'

# 5. Parar el generador al terminar
docker compose down
```

La ruta `infra/sesion1` de la diapositiva no coincide con la estructura de este repositorio (`infra/base` y `demo1-ingesta/infra`). Anótalo en `CAMBIOS_DIAPOSITIVAS.md` con la ruta correcta. `gunzip`, `head` y `jq` no existen por defecto en Windows: `comprobar_bronze.py` debe cubrir lo mismo.
