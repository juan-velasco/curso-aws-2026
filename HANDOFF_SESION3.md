# Handoff: código de las demos y ejercicios de la sesión 3 · Curso AWS para HP

> **Para el profesor.** Copia este fichero en la raíz del repositorio como `HANDOFF_SESION3.md`, junto a `ESTADO_SESION1.md` y `ESTADO_SESION2.md`, y pide a Claude Code: *«Lee HANDOFF_SESION3.md, ESTADO_SESION1.md y ESTADO_SESION2.md y construye la sesión 3 siguiendo el plan de trabajo. Pregúntame antes de cualquier acción que cree, modifique o borre recursos en AWS»*. Usa la misma cuenta de pruebas.

---

## 1. Contexto y alcance

El repositorio ya contiene las demos 1 a 4 (sesiones 1 y 2), probadas contra AWS. `ESTADO_SESION1.md` y `ESTADO_SESION2.md` describen su estado real y **prevalecen sobre los handoffs anteriores**.

La **sesión 3** tiene dos demos y dos ejercicios con código. Los ejercicios son independientes del lago de datos.

| Pieza | Qué enseña | Depende de |
|---|---|---|
| **Demo 5 · La API de ventas en ECS con Fargate** | ECR, task definition, task role sin claves, Fargate en subred pública | La imagen de `demo1-ingesta/api` y el stream de Firehose |
| **Demo 6 · Previsión de ventas con SageMaker** | Studio, UNLOAD desde gold, features, split temporal, XGBoost, WAPE, previsión a gold y visual en QuickSight | `gold.mv_ventas_diarias` y `gold.dim_fecha` en Redshift, Amazon Quick |
| **Ejercicio F · Proteger una API con Cognito** | User pool, app client, API Gateway con autorizador Cognito, JWT | Nada |
| **Ejercicio G · GuardDuty e Inspector** | Hallazgos de ejemplo, regla de EventBridge hacia SNS, escaneo de imágenes en ECR | La imagen de la API en ECR (demo 5) |

El ejercicio E (plan de compra) es de papel y no necesita código. AWS Batch se explica en las diapositivas, pero **no tiene demo**: queda fuera de alcance.

El código y los pasos de las diapositivas están en el **anexo A**. El repositorio debe respetarlos; lo que no sea posible o tenga una forma mejor se anota en `CAMBIOS_DIAPOSITIVAS.md` (§10).

### Restricciones generales (las mismas de siempre)

- **Coste mínimo.** Cada alumno usa su propia cuenta de empresa. Nada con coste por hora queda encendido al terminar una demo: servicio de ECS a 0 tareas, space de Studio parado, **ningún endpoint de SageMaker**.
- **Multiplataforma.** Scripts en Python, no en bash. En los guiones, comandos en bash y en PowerShell si difieren.
- **Idioma.** README, guiones, comentarios y logs en español.
- **Sin secretos en git.** Contraseñas de usuarios de prueba por variable de entorno o petición interactiva, nunca en ficheros.
- **No romper lo existente.** `pytest`, `ruff`, `terraform fmt` y `terraform validate` de las sesiones 1 y 2 deben seguir pasando.

---

## 2. Decisiones ya tomadas

| Tema | Decisión |
|---|---|
| Carpetas nuevas | `demo5-api-fargate/`, `demo6-prevision-sagemaker/`, `ejercicio-f-cognito/` y `ejercicio-g-guardduty-inspector/` |
| Etiquetas | `proyecto = curso-aws-hp`, `sesion = 3`, `demo = demo5 \| demo6 \| ejercicio-f \| ejercicio-g` |
| Estado de Terraform | Local; los módulos nuevos leen `infra/base` (y lo que necesiten de demo4) con `terraform_remote_state` |
| Demo 5: qué hace Terraform y qué hace la demo | Terraform crea **red, roles y log group**. El repositorio de ECR, el cluster, la task definition y el service se crean **en la demo con los comandos de la diapositiva**. Un script de limpieza los borra |
| Demo 5: red | VPC propia mínima: 2 subredes públicas, internet gateway, sin NAT ni balanceador. Security group: puerto 8000 solo desde `mi_ip` |
| Demo 5: execution role | Rol propio `curso-aws-hp-ecs-ejecucion` con `AmazonECSTaskExecutionRolePolicy`. **No usar `ecsTaskExecutionRole`**: en una cuenta de empresa puede existir y ser compartido |
| Demo 6: datos | Los 120 días reales de gold. Resultados no realistas: no importa, lo que importa es que la demo se ejecute |
| Demo 6: previsión | Grano **país × familia × día**, 28 días. AWS Batch la repartiría por tienda (solo en diapositivas) |
| Demo 6: clima | **Sintético** y determinista, por país y día, generado por un script |
| Demo 6: ruta principal | Todo en el notebook (entrenar, evaluar, prever). Training job en Spot, Model Registry y batch transform como **ruta opcional** |
| Demo 6: sin endpoints | Ningún endpoint en tiempo real, ni siquiera de prueba |
| Ejercicio F | API REST con **integración mock**, sin Lambda |
| Ejercicio G | Solo activar lo que no esté activo. Si GuardDuty o Inspector los gestiona la organización, no tocarlos (§7.1) |

---

## 3. Lo que hay que tener en cuenta de las sesiones anteriores

- **Imagen de la API:** `demo1-ingesta/api`, `python:3.12-slim`, `USER 1000`, `ENV HOME=/tmp`, puerto 8000, `/health`.
  - **La API exige `AWS_REGION`** y no arranca sin ella: la task definition debe incluirla, aunque la diapositiva 10 no la muestra.
  - **El contexto de build** es `demo1-ingesta/api/`, no la raíz.
- **Stream** `hp-retail-ventas`. La política `api-ventas-firehose-put` de la sesión 1 (solo `PutRecord` y `PutRecordBatch` sobre el stream) debería existir: compruébalo en los outputs de `demo1-ingesta/infra` y **reutilízala** en el task role. Si no existe, créala igual.
- **Generador** (`demo1-ingesta/generador`): admite `API_URL`. Para apuntarlo a Fargate sin levantar la API local, usar `docker compose run --rm --no-deps -e API_URL=http://<ip>:8000 generador`, o lo que funcione mejor con el compose actual.
- **Redshift Serverless** `hp-retail`, base de datos `dev`, accesible desde internet.
  - El rol por defecto del namespace (`curso-aws-hp-redshift`) solo lee `silver/`. Para UNLOAD y COPY hay que **añadirle lectura y escritura sobre `ml/*`** en `demo4-pipeline/infra` (pregunta antes de aplicar).
  - Se ejecuta SQL con `comun/redshift.py`.
- **`gold.mv_ventas_diarias`:** `fecha_sk`, `pais`, `familia`, `color`, `talla`, `unidades`, `venta_neta`. Unos 101.750 registros de 120 días, del 02-07-2026 al 29-10-2026.
- **`gold.dim_fecha`:**
  - Columnas del calendario de la sesión 2: `fecha_sk`, `fecha`, `anio`, `mes`, `nombre_mes`, `semana_iso`, `dia_semana`, `nombre_dia`, `es_fin_de_semana`, `temporada`, `es_rebajas`, `es_festivo`.
  - **Los nombres de columna del notebook deben ser exactamente estos.**
  - Comprueba los tipos reales de `es_rebajas`, `es_festivo` y `temporada` y conviértelos a entero o `category` en el notebook.
- **El histórico no tiene efecto del clima** (el backfill solo modela fin de semana, rebajas y estacionalidad por familia). El clima sintético no mejorará el modelo; es aceptable.
- **Amazon Quick** está activa desde el 30-10-2026 y su prueba acaba el 29-11-2026. Fuente de datos `curso-redshift-gold` creada en `demo4-pipeline/infra`. Si la sesión 3 se imparte después de cancelarla, el paso 6 de la demo 6 se muestra con capturas.
- **Usuarios de Redshift:** `quicksight_ro` ve gold a través del rol `lector_gold_completo` (con `IGNORE RLS`). Cualquier tabla o vista nueva necesita su `GRANT SELECT`.

---

## 4. Estructura del repositorio

```
curso_aws_hp/
├── HANDOFF_SESION3.md
├── demo5-api-fargate/
│   ├── GUION.md
│   ├── infra/                    # red, roles de ejecución y de tarea, log group
│   ├── taskdef.json.tpl          # plantilla de la task definition de la diapositiva 10
│   └── scripts/                  # generar_taskdef.py, ip_tarea.py, comprobar_demo5.py, limpiar_demo5.py
├── demo6-prevision-sagemaker/
│   ├── GUION.md                  # incluye el guion del visual de QuickSight (anexo B)
│   ├── infra/                    # red, dominio y perfil de Studio, rol de ejecución, dataset de QuickSight
│   ├── sql/                      # unload.sql, fct_prevision.sql, v_prevision_vs_real.sql
│   ├── notebooks/
│   │   └── prevision_ventas.ipynb
│   ├── sagemaker/                # entrenar.py, inferencia.py (ruta opcional)
│   └── scripts/                  # generar_clima.py, preparar_datos.py, cargar_prevision.py,
│                                 # lanzar_entrenamiento.py, registrar_publicar.py, comprobar_demo6.py, limpiar_demo6.py
├── ejercicio-f-cognito/
│   ├── SOLUCION.md
│   ├── infra/                    # user pool, app client, grupo, API REST con mock y autorizador
│   └── scripts/                  # crear_usuario.py, probar_api.py
└── ejercicio-g-guardduty-inspector/
    ├── SOLUCION.md
    ├── infra/                    # detector de GuardDuty, regla de EventBridge, SNS, Inspector para ECR, repositorio de ECR
    └── scripts/                  # estado_servicios.py, hallazgos_ejemplo.py, subir_imagenes.py, resumen_inspector.py
```

---

## 5. Demo 5 · La API de ventas en ECS con Fargate

### 5.1 Infraestructura (`demo5-api-fargate/infra/`)

- **Red:** VPC `10.40.0.0/16`, 2 subredes públicas en 2 zonas, internet gateway, sin NAT. Security group `api-ventas`: entrada 8000/tcp solo desde `mi_ip` (detectada como en las demos anteriores) y salida libre.
- **Execution role** `curso-aws-hp-ecs-ejecucion` con `AmazonECSTaskExecutionRolePolicy`.
- **Task role** `api-ventas-task`:
  - Confía en `ecs-tasks.amazonaws.com`.
  - Lleva **solo** la política `api-ventas-firehose-put` (la de la diapositiva 11).
  - Condición `aws:SourceAccount` en la relación de confianza.
- **Log group** `/ecs/api-ventas` con retención de 7 días.
- **Outputs:** `subredes`, `security_group`, `execution_role_arn`, `task_role_arn`, `log_group`, `region`, `account_id` y `stream_name`.

### 5.2 Task definition (`taskdef.json.tpl` y `generar_taskdef.py`)

La de la diapositiva 10, con los ARN reales de los outputs (`generar_taskdef.py` escribe `taskdef.json`, que no va a git). Dos cambios necesarios, que hay que anotar:

- `environment` incluye **`AWS_REGION`** además de `FIREHOSE_STREAM`, porque la API no arranca sin ella.
- `executionRoleArn` apunta a `curso-aws-hp-ecs-ejecucion`.

Mantén `cpu 256`, `memory 512`, `ARM64`, puerto 8000 y `awslogs`.

### 5.3 Pasos de la demo (comandos de la diapositiva 15)

1. **Imagen.** Desde `demo1-ingesta/api/`: `aws ecr create-repository --repository-name api-ventas` (con `--image-scanning-configuration scanOnPush=true`), login y `docker buildx build --platform linux/arm64 --push -t …/api-ventas:1.0.0 .`. En portátiles x86, Docker Desktop emula ARM64 con QEMU: comprueba que funciona y cuánto tarda.
2. **Task role:** ya lo crea Terraform. En la demo se muestra en la consola: política, recurso acotado y relación de confianza.
3. **Cluster, task definition y service:** `create-cluster`, `register-task-definition` y `create-service` con `--launch-type FARGATE`, `desired-count 1` y la red de los outputs.
4. **IP pública:** `ip_tarea.py` la obtiene (lista la tarea, lee la ENI y muestra la IP pública). Después se lanza el generador contra `http://<ip>:8000` unos minutos.
5. **Logs y datos:** logs en `/ecs/api-ventas` y ficheros nuevos en `bronze/ventas/` de hoy.
6. **Cerrar:** `update-service --desired-count 0`.

### 5.4 Scripts

- **`comprobar_demo5.py`** comprueba:
  - tarea en `RUNNING`;
  - `GET /health` responde 200 desde el equipo;
  - el log group tiene streams recientes;
  - hay ficheros nuevos en bronze desde la hora de inicio;
  - la task definition **no** contiene variables `AWS_ACCESS_KEY_ID` ni `AWS_SECRET_ACCESS_KEY`.
- **`limpiar_demo5.py`:**
  - Por defecto deja el service a 0.
  - Con `--todo` borra el service y el cluster, da de baja las revisiones de la task definition y borra el repositorio de ECR. Antes de borrar el repositorio, avisa de que lo usa el ejercicio G.

### 5.5 Criterios de aceptación (diapositiva «Qué comprobar»)

- [ ] Tarea en estado RUNNING.
- [ ] `/health` responde desde tu equipo.
- [ ] Logs en `/ecs/api-ventas`.
- [ ] Nuevos ficheros en `bronze/ventas`, y la demo 4 los procesa sin cambios.
- [ ] Sin claves AWS en la tarea: las credenciales vienen del task role.
- [ ] Con `desired-count 0`, ninguna tarea en marcha.
- [ ] Coste de una demo de 30 minutos (Fargate 0,25 vCPU / 0,5 GB y logs): céntimos. Anótalo en el GUION.

---

## 6. Demo 6 · Previsión de ventas con SageMaker

### 6.1 Infraestructura (`demo6-prevision-sagemaker/infra/`)

- **Red:** VPC `10.50.0.0/16` con 2 subredes públicas, sin NAT. El dominio de Studio necesita VPC aunque use acceso público a internet.
- **Dominio de SageMaker** `curso-aws-hp`:
  - Autenticación IAM y `app_network_access_type = PublicInternetOnly`.
  - Retención del EFS del dominio en `Delete`, para que `destroy` no deje volúmenes.
  - **Apagado por inactividad de JupyterLab** a 60 minutos (gestión del ciclo de vida de apps del dominio). Si el proveedor no lo admite, usa una lifecycle configuration y documéntalo.
  - Tipo de instancia por defecto `ml.t3.medium`.
- **Perfil de usuario** `profesor`. El space de JupyterLab se crea en la demo, desde la consola.
- **Rol de ejecución de Studio** `curso-aws-hp-sagemaker`:
  - `AmazonSageMakerFullAccess`.
  - Política propia de lectura y escritura sobre `s3://<bucket>/ml/*` y `ListBucket` con prefijo `ml/`.
  - Nada más del bucket.
- **Permisos del rol de Redshift:** añade en `demo4-pipeline/infra` lectura y escritura sobre `ml/*` al rol `curso-aws-hp-redshift`, para UNLOAD y COPY.
- **QuickSight** (detrás de `quicksight_activo`, por defecto `false`): dataset SPICE `prevision_vs_real` sobre `gold.v_prevision_vs_real`, con la fuente de datos de demo4 (léela de su estado) y permisos para `quicksight_usuario_arn`.
- **Outputs:** `dominio_id`, `perfil`, `rol_ejecucion_arn`, `url_studio` (si se puede obtener) y `quicksight_dataset_id`.

### 6.2 SQL (`demo6-prevision-sagemaker/sql/`)

- **`unload.sql`:** los dos UNLOAD de la diapositiva 49, con el bucket real y **`ALLOWOVERWRITE`** (o `CLEANPATH`) para poder repetir la demo. Sin eso, el segundo UNLOAD falla. Anótalo.
- **`fct_prevision.sql`:** `gold.fct_prevision` con `fecha_calculo` (date), `fecha_sk` (día previsto), `pais`, `familia` y `unidades_previstas` (decimal(12,2)). DISTSTYLE ALL y SORTKEY (`fecha_calculo`, `fecha_sk`). `GRANT SELECT` para `lector_gold_completo`.
- **`v_prevision_vs_real.sql`:** vista por `fecha_sk`, `pais` y `familia` con:
  - `unidades_reales`, la suma de `mv_ventas_diarias`, nula en los días futuros;
  - `unidades_previstas`, de la `fecha_calculo` más reciente;
  - `fecha` desde `dim_fecha`.

  `GRANT SELECT` igual.

### 6.3 Clima sintético (`scripts/generar_clima.py`)

- **Rango:** una fila por país (ES, FR, US, JP, CN) y día, desde la primera fecha de `mv_ventas_diarias` hasta 28 días después de la última. Debe cubrir los días que se prevén.
- **Columnas:** `fecha_sk`, `pais`, `temp_media` (°C) y `lluvia_mm`.
- **Generación:** determinista (semilla fija); temperatura con estacionalidad anual según el país y algo de ruido, lluvia con días secos y días de lluvia.
- **Salida:** un Parquet en `s3://<bucket>/ml/clima/`. Documenta que es inventado.

### 6.4 Preparar los datos (`scripts/preparar_datos.py`)

Ejecuta `unload.sql` con la Data API (`comun/redshift.py`) y comprueba que `ml/ventas_diarias/` y `ml/calendario/` tienen ficheros. Así el paso 2 de la demo se puede lanzar desde la terminal y luego enseñarse en el notebook.

### 6.5 Notebook (`notebooks/prevision_ventas.ipynb`)

**Autocontenido:** no importa nada del repositorio, porque se sube a Studio a mano o con un `git clone`. Una celda de parámetros con el bucket y la región. Si a la imagen de Studio le falta algo (s3fs, xgboost), una celda `%pip install` con versiones fijas.

Secciones, siguiendo las diapositivas 49, 50, 55, 58 y 60 (código en el anexo A):

1. **Carga:**
   - `ventas`, `cal` y `clima` desde `ml/`.
   - Merge de `cal` **solo por `fecha_sk`** y de `clima` por `fecha_sk` y `pais`.
   - `fecha` como datetime.
2. **Serie completa:** rejilla de todos los días × país × familia, con 0 unidades donde no haya venta.
3. **Features** con los nombres del repositorio:
   - `dia_semana`, `semana_iso`, `mes`, `temporada`, `es_festivo`, `es_rebajas`, `temp_media`, `lluvia_mm`, `pais` y `familia`.
   - `lag_28` y `lag_364`, desplazando por serie. `lag_364` saldrá vacío con 120 días: se deja, XGBoost acepta NaN.
   - `media_28`: media de 28 días **desplazada 28 días**, para no usar datos que no se conocerían al prever.
   - `pais`, `familia` y `temporada` como `category`; booleanos a entero.
4. **Split temporal** exactamente como en la diapositiva 55: `corte = df.fecha.max() - pd.Timedelta(days=28)`; `train = fecha <= corte`; `valid = fecha > corte`.
5. **Línea base:** media de las 4 semanas anteriores al corte por serie, aplicada a todo el periodo de validación. WAPE de la línea base.
6. **Modelo** con los hiperparámetros de la diapositiva 55, entrenado dos veces, **con y sin clima**. WAPE de cada uno, tabla resumen y gráfico de barras como el de la diapositiva 58.
7. **Importancia de features** (gain) en un gráfico.
8. **Previsión de 28 días:**
   - Fechas del día siguiente al máximo hasta +28, por país y familia, con calendario, clima sintético, `lag_28` y `media_28` calculados con ventas reales. Todos los retardos de 28 días caen en días conocidos.
   - Salida en `ml/predicciones/fecha_calculo=AAAA-MM-DD/prevision.csv` con `fecha_calculo`, `fecha_sk`, `pais`, `familia` y `unidades_previstas`.
9. **(Opcional)** Escribir `ml/train/` y `ml/valid/` para la ruta del training job.

### 6.6 Cargar la previsión en gold (`scripts/cargar_prevision.py`)

Con la Data API:

- `DELETE` de la `fecha_calculo` que se carga y `COPY` del CSV desde `ml/predicciones/fecha_calculo=…/` con `IAM_ROLE default`, `CSV` e `IGNOREHEADER 1`. Es idempotente.
- Si QuickSight está activo, refresca el dataset `prevision_vs_real` con `create_ingestion`.

### 6.7 Ruta opcional: training job, Model Registry y batch transform

Para demostrar las diapositivas 56 y 57 si hay tiempo. Debe funcionar, pero no es imprescindible.

- **Versión del SDK.** Comprueba qué versión del SDK de SageMaker trae la imagen de Studio. El código de la diapositiva 56 usa la API clásica de estimadores. Si Studio trae una versión mayor que la cambia, fija en el notebook o en los scripts la versión que admite ese código y anótalo. Comprueba también que el contenedor de XGBoost `1.7-1` sigue disponible en `eu-west-1` y admite `enable_categorical`.
- **`sagemaker/entrenar.py`:**
  - Script mode: lee los canales `train` y `validation`, aplica las mismas categorías y features y entrena con los hiperparámetros recibidos.
  - Guarda el modelo y las listas de categorías en `model_dir`.
  - Usa checkpoints en `/opt/ml/checkpoints`.
- **`sagemaker/inferencia.py`:** `model_fn`, `input_fn`, `predict_fn` y `output_fn`. Convierte el CSV de entrada a DataFrame con las **mismas categorías del entrenamiento**, porque sin ellas el batch transform falla con columnas categóricas.
- **`scripts/lanzar_entrenamiento.py`:**
  - El estimador de la diapositiva 56: `ml.m5.large` en **Spot**, `max_run 900`, `max_wait 1800` y checkpoints en `ml/checkpoints/`.
  - Se lanza desde Studio o desde el portátil con el rol de Studio.
- **`scripts/registrar_publicar.py`:**
  - Registra el modelo en el grupo `prevision-ventas` con estado `PendingManualApproval` y el WAPE como métrica.
  - Lo aprueba solo si su WAPE es menor que el de la línea base (parámetro).
  - Lanza un **batch transform desde la versión aprobada** (no desde el estimador), en `ml.m5.large`, con salida en `ml/predicciones_bt/`.
- **Nunca** `deploy()` ni endpoints.

### 6.8 Scripts de comprobación y limpieza

- **`comprobar_demo6.py`:**
  - Ficheros en `ml/ventas_diarias/`, `ml/calendario/`, `ml/clima/` y `ml/predicciones/`.
  - `gold.fct_prevision` con **28 días por serie** para la última `fecha_calculo`: 5 países × 8 familias × 28 días = 1.120 filas, si existen todas las combinaciones.
  - `v_prevision_vs_real` devuelve filas.
  - **Ningún endpoint** (`list-endpoints` vacío) y ninguna app de Studio en estado `InService`.
- **`limpiar_demo6.py`:**
  - Para las apps y spaces del dominio y comprueba que no hay endpoints.
  - Con `--todo`, borra los spaces y los modelos registrados, como paso previo a `terraform destroy` al terminar el curso.

### 6.9 Criterios de aceptación (diapositiva «Qué comprobar»)

- [ ] El notebook se ejecuta de principio a fin en un space `ml.t3.medium`, sin errores, con los 120 días reales.
- [ ] El modelo gana a la línea base. Si con estos datos no gana, no es bloqueante: documéntalo y no fuerces el resultado.
- [ ] El gráfico de importancia de features se genera. «Calendario > clima» debería cumplirse, porque el clima es aleatorio.
- [ ] `gold.fct_prevision` con 28 días por serie.
- [ ] Visual de real frente a previsto en QuickSight (anexo B), si Amazon Quick sigue activa.
- [ ] Space de Studio detenido y ningún endpoint.
- [ ] Ruta opcional: training job en Spot terminado, versión aprobada en el registry y batch transform con salida en S3.
- [ ] El coste de la demo (space unas 2 horas, UNLOAD, COPY y la ruta opcional) queda en el GUION. Debe estar en el orden de 1 $.

---

## 7. Ejercicios de seguridad

### 7.1 Precaución en cuentas de empresa

GuardDuty e Inspector suelen estar **activados y gestionados por la organización** (cuenta de administrador delegado). Antes de crear nada, `ejercicio-g-guardduty-inspector/scripts/estado_servicios.py` debe mostrar:

- si hay detector de GuardDuty y quién lo administra;
- el estado de Inspector por tipo de recurso.

Terraform **solo crea lo que no exista**, con variables `crear_detector_guardduty` y `activar_inspector_ecr` decididas a partir de ese estado. **Nunca desactiva un servicio que no haya activado él.** Si el servicio lo gestiona la organización, el ejercicio se limita a explorar hallazgos, y así se explica en `SOLUCION.md`.

### 7.2 Ejercicio F · Cognito (`ejercicio-f-cognito/`)

**Infraestructura:**

- **User pool** `tiendas`: inicio de sesión por nombre de usuario, MFA desactivado y política de contraseñas por defecto.
- **App client** público, sin secreto, con `ALLOW_USER_PASSWORD_AUTH` y `ALLOW_REFRESH_TOKEN_AUTH`.
- **Grupo** `tiendas`.
- **API REST** `curso-hola` con el recurso `GET /hola`:
  - **Integración mock** que devuelve 200 y un JSON con un saludo, el usuario (`$context.authorizer.claims['cognito:username']`) y sus grupos, mediante una plantilla de mapeo.
  - Autorizador de tipo `COGNITO_USER_POOLS` sobre la cabecera `Authorization`.
  - Etapa `prod`.
- **Outputs:** `user_pool_id`, `client_id` y `url_api`.

**Scripts:**

- **`crear_usuario.py`:** crea el usuario `tienda-vlc-003` con `admin-create-user` y `admin-set-user-password --permanent`, lo añade al grupo y pide la contraseña de forma interactiva o la lee de una variable de entorno.
- **`probar_api.py`:**
  - Llama sin token y espera un 401.
  - Obtiene el ID token con `initiate-auth` y llama con él: espera un 200.
  - Decodifica el token sin verificar la firma y muestra `sub`, `cognito:groups`, `token_use`, `iss` y `exp`.

  Son los pasos de la diapositiva 67.

**`SOLUCION.md`:** la tabla de la solución de las diapositivas, con los comandos de la consola y de la CLI equivalentes a lo que hace Terraform, para quien lo haga a mano.

### 7.3 Ejercicio G · GuardDuty e Inspector (`ejercicio-g-guardduty-inspector/`)

**Infraestructura:**

- **Detector de GuardDuty** (solo si no existe).
- **Regla de EventBridge** con el patrón de la diapositiva 72 (severidad ≥ 7) hacia el tema SNS `curso-aws-hp-seguridad`, con suscripción por email (variable `email_alertas`).
- **Inspector:** escaneo de ECR (solo si no está activo).
- **Repositorio de ECR** `curso-imagen-antigua`, con `force_delete`.

**Scripts:**

- **`hallazgos_ejemplo.py`:** `create-sample-findings` en el detector y recuento de hallazgos `[SAMPLE]` por severidad.
- **`subir_imagenes.py`:** descarga `python:3.8`, la etiqueta y la sube a `curso-imagen-antigua`. Recuerda que la imagen slim de la API ya está en `api-ventas` desde la demo 5.
- **`resumen_inspector.py`:**
  - Espera a que terminen los escaneos de las dos imágenes, con tiempo límite y mensajes de progreso.
  - Muestra los hallazgos por severidad de cada imagen y los 5 paquetes con más CVE.

**`SOLUCION.md`:**

- Las respuestas esperadas: hallazgos críticos por imagen, paquete con más CVE y email recibido.
- La **limpieza**: `destroy` desactiva solo lo que se activó y borra el repositorio. Recuerda los periodos de prueba (30 días GuardDuty, 15 días Inspector).

### 7.4 Criterios de aceptación

- [ ] **F:** 401 sin token, 200 con token y el grupo `tiendas` en el token decodificado.
- [ ] **G:**
  - hallazgos de ejemplo generados;
  - email recibido para uno de severidad alta (tras confirmar la suscripción);
  - Inspector muestra muchos más hallazgos en `python:3.8` que en la imagen de la API;
  - tras `destroy`, el estado de los servicios coincide con el inicial que mostró `estado_servicios.py`.

---

## 8. Pendientes de la sesión 2 (opcionales, con confirmación)

`ESTADO_SESION2.md` deja abiertas estas comprobaciones. Hazlas solo si el profesor lo confirma:

1. **RLS de `analista_asia`.** Crear un usuario temporal de Redshift con ese rol, comprobar que solo ve JP y CN en una consulta que una `fct_ventas` con `dim_tienda`, y borrarlo.
2. **Cuarentena.**
   - Escribir en bronze un fichero pequeño con eventos defectuosos (sin pasar por la API) y ejecutar la máquina de estados.
   - Comprobar `ventas_cuarentena` y la rama `pct_cuarentena > 5` → `NotificarFallo`.
   - Documentar cómo se limpia después.
3. **Lake Formation** sigue aplicado en la cuenta de pruebas. Pregunta si se destruye antes de empezar (con `-parallelism=1`): la sesión 3 no lo necesita.
4. **Amazon Quick:** recordar en el GUION de la demo 6 que hay que cancelarla antes del 29-11-2026, con `quicksight_activo = false` en demo4 y demo6 y aplicar antes de cancelar.

---

## 9. Plan de trabajo y reglas para Claude Code

### Reglas

- **Pregunta antes** de cualquier `terraform apply` o `destroy` y de cualquier acción que cree, modifique o borre recursos en AWS. Muestra el resumen del plan e indica qué tiene coste por hora o por uso.
- **GuardDuty e Inspector:** muestra el estado actual (`estado_servicios.py`) y lo que vas a cambiar, y espera confirmación explícita.
- **SageMaker:** nunca crees endpoints. Al terminar cada prueba, comprueba que no queda ninguna app en `InService` ni ningún training o transform job en curso.
- No toques recursos que no haya creado este repositorio.
- Mismas versiones que las sesiones anteriores salvo necesidad.
- `pytest`, `ruff`, `terraform fmt` y `terraform validate` en verde antes de dar algo por terminado.
- **Tests locales sin AWS:**
  - generación del clima (determinista, rangos, cobertura de fechas);
  - construcción de features (desplazamientos sin fuga, rejilla completa);
  - split y línea base;
  - plantilla de la task definition (incluye `AWS_REGION` y no incluye claves);
  - decodificación del JWT.

### Orden

1. **Demo 5:**
   - infraestructura (plan → **preguntar** → apply);
   - imagen ARM64, task definition y service;
   - comprobaciones y limpieza a 0 tareas.
2. **Permisos `ml/*`** para el rol de Redshift en demo4 (plan → **preguntar** → apply).
3. **Demo 6, datos:** SQL de gold, `generar_clima.py` y `preparar_datos.py`.
4. **Demo 6, notebook:**
   - infraestructura de Studio (plan → **preguntar** → apply);
   - ejecutar el notebook completo en Studio;
   - `cargar_prevision.py`;
   - comprobar y parar el space.
5. **Demo 6, QuickSight:** dataset y refresco, si Amazon Quick sigue activa.
6. **Demo 6, ruta opcional:** training job en Spot, registry y batch transform.
7. **Ejercicio F.**
8. **Ejercicio G:** primero `estado_servicios.py`, luego **preguntar**.
9. **Pendientes de la sesión 2** que confirme el profesor (§8).
10. Guiones, `SOLUCION.md`, README, `CAMBIOS_DIAPOSITIVAS.md` y `ESTADO_SESION3.md`, con el mismo formato que los anteriores. Incluye en este último **todo lo que sigue desplegado con coste** y cómo destruirlo al terminar el curso.

---

## 10. `CAMBIOS_DIAPOSITIVAS.md`

Añade una sección **Sesión 3** con el formato `diapositiva | texto actual | texto propuesto | motivo`. Incluye al menos:

- **Diapositiva 10:** `AWS_REGION` en `environment` y execution role propio en lugar de `ecsTaskExecutionRole`.
- **Diapositiva 15:** el build se lanza desde `demo1-ingesta/api/`; `create-repository` con `scanOnPush`.
- **Diapositiva 49:** `ALLOWOVERWRITE` o `CLEANPATH` en los UNLOAD.
- **Diapositiva 56:** versión del SDK y del contenedor de XGBoost, si cambian.
- Todo lo que no coincida al probar.

Las diapositivas de seguridad (65 en adelante) **aún no las ha revisado el profesor**: si algo del ejercicio F o G no encaja, anótalo igual y sigue el código de este handoff.

---

## 11. Fuera de alcance

- AWS Batch (array job de reposición y dimensionado): solo diapositivas.
- Capacity providers con Fargate Spot, balanceador y autoescalado del service: solo diapositivas.
- SageMaker Pipelines, Model Monitor, Feature Store y MLflow: solo diapositivas.
- `gold.fct_stock_diario`: ejemplo ilustrativo.
- Regenerar el histórico con más años o con efecto del clima.

---

## Anexo A · Código y pasos tal como aparecen en las diapositivas de la sesión 3

### Diapositiva 10 · Task definition de la API de ventas

```json
{
  "family": "api-ventas",
  "requiresCompatibilities": ["FARGATE"],
  "networkMode": "awsvpc",
  "cpu": "256",
  "memory": "512",
  "runtimePlatform": { "cpuArchitecture": "ARM64", "operatingSystemFamily": "LINUX" },
  "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::123456789012:role/api-ventas-task",
  "containerDefinitions": [{
    "name": "api",
    "image": "123456789012.dkr.ecr.eu-west-1.amazonaws.com/api-ventas:1.0.0",
    "portMappings": [{ "containerPort": 8000 }],
    "environment": [{ "name": "FIREHOSE_STREAM", "value": "hp-retail-ventas" }],
    "logConfiguration": { "logDriver": "awslogs", "options": {
      "awslogs-group": "/ecs/api-ventas", "awslogs-region": "eu-west-1",
      "awslogs-stream-prefix": "api" } }
  }]
}
```

### Diapositiva 11 · Política del task role

En la diapositiva, el ARN está partido en dos líneas para que quepa; en la política real va en una sola.

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "firehose:PutRecord",
      "firehose:PutRecordBatch"
    ],
    "Resource": "arn:aws:firehose:eu-west-1:123456789012:deliverystream/hp-retail-ventas"
  }]
}
```

### Diapositiva 14 · Demo 5: pasos

1. Crear el repositorio en ECR y subir la imagen para ARM64 con `docker buildx`.
2. Crear el task role con permiso solo sobre el stream de Firehose.
3. Registrar la task definition y crear cluster y service con 1 tarea.
4. Obtener la IP pública de la tarea y apuntar el generador: `API_URL=http://<ip>:8000`.
5. Ver los logs en CloudWatch y los datos nuevos en bronze.
6. Bajar el servicio a 0 tareas al terminar.

Qué comprobar: tarea en estado RUNNING · `/health` responde desde tu equipo · logs en `/ecs/api-ventas` · nuevos ficheros en `bronze/ventas` · sin claves AWS en la tarea.

### Diapositiva 15 · Demo 5: comandos

```bash
# 1. Imagen en ECR (ARM64)
aws ecr create-repository --repository-name api-ventas
aws ecr get-login-password | docker login --username AWS \
  --password-stdin $CUENTA.dkr.ecr.eu-west-1.amazonaws.com
docker buildx build --platform linux/arm64 --push \
  -t $CUENTA.dkr.ecr.eu-west-1.amazonaws.com/api-ventas:1.0.0 .

# 2. Cluster, task definition y service
aws ecs create-cluster --cluster-name hp-retail
aws ecs register-task-definition --cli-input-json file://taskdef.json
aws ecs create-service --cluster hp-retail --service-name api-ventas \
  --task-definition api-ventas --desired-count 1 --launch-type FARGATE \
  --network-configuration \
  "awsvpcConfiguration={subnets=[$SUBNET],securityGroups=[$SG],assignPublicIp=ENABLED}"

# 3. Al terminar: sin tareas, sin coste de cómputo
aws ecs update-service --cluster hp-retail --service api-ventas \
  --desired-count 0
```

### Diapositiva 49 · De gold a un dataset de entrenamiento

```sql
-- En Redshift: serie diaria y calendario a S3 en Parquet
UNLOAD ('SELECT fecha_sk, pais, familia,
                SUM(unidades) AS unidades
         FROM gold.mv_ventas_diarias GROUP BY 1, 2, 3')
TO 's3://retail-company-datalake-prod/ml/ventas_diarias/'
IAM_ROLE default FORMAT AS PARQUET;
UNLOAD ('SELECT * FROM gold.dim_fecha')
TO 's3://retail-company-datalake-prod/ml/calendario/'
IAM_ROLE default FORMAT AS PARQUET;
```

```python
# En el notebook de SageMaker Studio
import pandas as pd
base = "s3://retail-company-datalake-prod/ml"
ventas = pd.read_parquet(f"{base}/ventas_diarias/")
cal = pd.read_parquet(f"{base}/calendario/")   # gold.dim_fecha
clima = pd.read_parquet(f"{base}/clima/")      # sintético
df = (ventas.merge(cal, on="fecha_sk", how="left")
            .merge(clima, on=["fecha_sk", "pais"], how="left"))
```

### Diapositiva 55 · Entrenar en el notebook

```python
import xgboost as xgb
# 1. Features y categóricas
features = ["dia_semana", "semana_iso", "mes", "temporada",
            "es_festivo", "es_rebajas", "temp_media", "lluvia_mm",
            "lag_28", "lag_364", "media_28", "pais", "familia"]
for c in ["pais", "familia", "temporada"]:
    df[c] = df[c].astype("category")

# 2. Split temporal: los últimos 28 días validan
corte = df.fecha.max() - pd.Timedelta(days=28)
train = df[df.fecha <= corte]
valid = df[df.fecha > corte]

# 3. Modelo
modelo = xgb.XGBRegressor(
    n_estimators=800, max_depth=6, learning_rate=0.05,
    objective="reg:tweedie", tree_method="hist",
    enable_categorical=True, early_stopping_rounds=50)

# 4. Entrenar vigilando la validación
modelo.fit(train[features], train["unidades"],
           eval_set=[(valid[features], valid["unidades"])])

# 5. Evaluar con WAPE
def wape(real, prev):
    return abs(real - prev).sum() / real.sum()
print(wape(valid["unidades"], modelo.predict(valid[features])))
```

### Diapositiva 56 · El mismo modelo como training job en Spot

```python
import sagemaker
from sagemaker.xgboost.estimator import XGBoost

# 1. Rol de ejecución y bucket
role = sagemaker.get_execution_role()
bucket = "retail-company-datalake-prod"

# 2. El código del notebook, como script
est = XGBoost(
    entry_point="entrenar.py",
    framework_version="1.7-1",
    role=role,
    # 3. Instancia temporal en Spot
    instance_type="ml.m5.large", instance_count=1,
    use_spot_instances=True,
    max_run=900, max_wait=1800,
    checkpoint_s3_uri=f"s3://{bucket}/ml/checkpoints/",
    # 4. Hiperparámetros
    hyperparameters={"max_depth": 6, "eta": 0.05})

# 5. Lanzar con los datos de S3
est.fit({"train": f"s3://{bucket}/ml/train/",
        "validation": f"s3://{bucket}/ml/valid/"})
```

### Diapositiva 57 · Registrar y publicar el modelo (conceptual, sin código)

Registrar (versión en el grupo `prevision-ventas` con sus métricas, pendiente de aprobar) → Aprobar (solo si el WAPE mejora a la línea base y a la versión en uso) → Publicar (batch transform **desde la versión aprobada**: lee features de S3, escribe la previsión y apaga la instancia) → Automatizar (SageMaker Pipelines). El script de inferencia prepara las columnas, incluidas las categóricas, igual que en el entrenamiento. Sin endpoints en tiempo real.

### Diapositiva 60 · Las predicciones vuelven al pipeline

Batch transform (28 días por país y familia) → `ml/predicciones/` en CSV → COPY a `gold.fct_prevision` → QuickSight (real frente a previsto) y AWS Batch (reparte la previsión por tienda). Una fila por país × familia × día previsto × fecha de cálculo.

### Diapositiva 62 · Demo 6: pasos

1. Abrir SageMaker Studio y arrancar un space de JupyterLab en `ml.t3.medium`.
2. UNLOAD de la serie diaria desde gold y carga de calendario y clima.
3. Features, split temporal y línea base (media de 4 semanas).
4. Entrenar XGBoost en el notebook y comparar WAPE con y sin clima.
5. Previsión de 28 días a S3 y COPY a `gold.fct_prevision`.
6. Visual de real frente a previsto en QuickSight; parar el space.

Qué comprobar: el modelo gana a la línea base · importancia de features coherente: calendario > clima · tabla `fct_prevision` con 28 días por serie · space de Studio detenido y ningún endpoint.

### Diapositiva 67 · Probar una API protegida con Cognito

```bash
# Obtener tokens (flujo USER_PASSWORD_AUTH: solo para laboratorio)
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id $CLIENT_ID \
  --auth-parameters USERNAME=tienda-vlc-003,PASSWORD=$PASSWORD

# Sin token: 401 Unauthorized
curl -i https://$API_ID.execute-api.eu-west-1.amazonaws.com/prod/hola

# Con token: 200 OK
curl -i -H "Authorization: $ID_TOKEN" \
  https://$API_ID.execute-api.eu-west-1.amazonaws.com/prod/hola

# Payload del ID token (decodificado)
{ "sub": "5f1c…", "cognito:groups": ["tiendas"], "token_use": "id",
  "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_AbC123",
  "exp": 1793270400 }
```

### Diapositivas 68 y 69 · Ejercicio F

Planteamiento: crear un user pool «tiendas» con login por nombre de usuario · un app client sin secreto con el flujo `USER_PASSWORD_AUTH` · un usuario de prueba y un grupo «tiendas» · una API REST en API Gateway con `GET /hola` (integración mock o Lambda) · un autorizador Cognito en el método.

Qué se pide: llamar sin token y obtener 401 · obtener el ID token con la CLI · llamar con token y obtener 200 · decodificar el token y localizar el grupo.

Solución: user pool con inicio de sesión por username · app client público sin secreto con `ALLOW_USER_PASSWORD_AUTH` · usuario con `admin-create-user` + `admin-set-user-password --permanent` (estado CONFIRMED) · autorizador de tipo Cognito sobre la cabecera `Authorization` (método con `COGNITO_USER_POOLS`) · API desplegada en la etapa `prod`.

### Diapositiva 72 · Respuesta automática a hallazgos graves

```json
{
  "source": ["aws.guardduty"],
  "detail-type": ["GuardDuty Finding"],
  "detail": {
    "severity": [{ "numeric": [">=", 7] }]
  }
}
```

### Diapositivas 75 y 76 · Ejercicio G

Planteamiento: GuardDuty: activarlo y usar «Generate sample findings» · explorar un hallazgo (recurso, severidad, recomendación) · crear la regla de EventBridge (severidad ≥ 7) hacia un tema SNS con tu email · Inspector: activar el escaneo de ECR · subir a ECR una imagen `python:3.8` y la imagen slim de la API.

Qué se pide: ¿cuántos hallazgos críticos tiene cada imagen? · ¿qué paquete concentra más CVE? · ¿llegó el email de un hallazgo de ejemplo? · desactivar ambos servicios al acabar.

Solución esperada: decenas de hallazgos `[SAMPLE]` de todos los tipos y severidades · email de SNS por cada hallazgo de ejemplo con severidad alta · `python:3.8` con muchos hallazgos, varios críticos, en paquetes del sistema operativo · la imagen slim de la API con muy pocos y ninguno crítico · GuardDuty suspendido o desactivado, Inspector desactivado e imágenes borradas.

Nota del orador: el escaneo de Inspector puede tardar unos minutos; conviene llevar las imágenes ya subidas y escaneadas.

---

## Anexo B · Guion del visual «real frente a previsto» en QuickSight (borrador)

Para `demo6-prevision-sagemaker/GUION.md`. Comprueba los nombres de menú en la consola de Amazon Quick.

1. Datasets → `prevision_vs_real` (SPICE): comprobar la fecha de la última actualización tras `cargar_prevision.py`.
2. Abrir el análisis de la demo 4 (o crear uno nuevo) y añadir el dataset.
3. **Gráfico de líneas:**
   - eje X: `fecha` (día);
   - valores: `unidades_reales` (suma) y `unidades_previstas` (suma).

   Las reales terminan el último día con datos; las previstas siguen 28 días más.
4. **Controles** para `pais` y `familia`. Mostrar una familia sensible al clima (abrigos o baño) en un país.
5. **Mensaje para la clase:**
   - lo previsto es la línea de la última fecha de cálculo;
   - cuando lleguen las ventas reales, la vista permitirá medir el WAPE según la antelación (diapositiva 60).
6. Si Amazon Quick ya no está activa, mostrar una captura preparada antes.
