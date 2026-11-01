# Curso AWS para HP · Del TPV al dashboard y la previsión

Código de las demos y ejercicios de las sesiones 1, 2 y 3 del curso de AWS (12 h, 3 sesiones) que imparte el ITI para HP. El hilo conductor es un **retail de moda global** cuyas ventas alimentan un lago de datos en S3 con arquitectura medallón (bronze, silver, gold).

| Demo | Qué enseña | Flujo |
|---|---|---|
| [Demo 1 · Del TPV a bronze](demo1-ingesta/GUION.md) | Ingesta en streaming de las ventas | Generador → API REST (FastAPI en Docker) → Amazon Data Firehose → S3 `bronze/ventas/` |
| [Demo 2 · CDC con DMS](demo2-cdc-dms/GUION.md) | Captura de cambios de clientes y productos | RDS PostgreSQL → AWS DMS (Full load + CDC) → S3 `bronze/cdc/` |
| [Demo 3 · Catálogo y Athena](demo3-catalogo-athena/GUION.md) | Glue Data Catalog, partition projection, coste por datos escaneados | S3 `bronze/` → Glue Data Catalog → Athena |
| [Demo 4 · Pipeline de punta a punta](demo4-pipeline/GUION.md) | Glue Jobs, Iceberg, SCD2, Data Quality, ELT, orquestación y dashboard | bronze → silver (Iceberg) → gold (Redshift Serverless) → QuickSight, con Step Functions |
| [Lake Formation](demo4-pipeline/GUION_LAKE_FORMATION.md) | LF-Tags y filtros de filas y columnas. **Solo el profesor, en una cuenta de pruebas** | Roles con *opt-in* en modo híbrido sobre `silver/` |
| [Demo 5 · La API en Fargate](demo5-api-fargate/GUION.md) | ECR, task definition y task role sin claves | Imagen ARM64 → ECS con Fargate → Firehose → `bronze/ventas/` |
| [Demo 6 · Previsión de ventas](demo6-prevision-sagemaker/GUION.md) | Studio, features, split temporal, XGBoost y WAPE. Sin endpoints | gold → UNLOAD → notebook → `gold.fct_prevision` → QuickSight |
| [Ejercicio F · Cognito](ejercicio-f-cognito/SOLUCION.md) | User pool, autorizador y JWT | API Gateway con mock y autorizador de Cognito |
| [Ejercicio G · GuardDuty e Inspector](ejercicio-g-guardduty-inspector/SOLUCION.md) | Hallazgos, EventBridge y escaneo de imágenes. **Primero, `estado_servicios.py`** | GuardDuty → EventBridge → SNS; Inspector sobre ECR |

Las diferencias con las diapositivas están en [CAMBIOS_DIAPOSITIVAS.md](CAMBIOS_DIAPOSITIVAS.md).

## Requisitos

- Una **cuenta de AWS de pruebas** (no la de producción) y un perfil de AWS CLI llamado `curso`:
  ```bash
  aws configure --profile curso          # claves de acceso de un usuario IAM
  aws configure sso --profile curso      # o con IAM Identity Center
  aws sts get-caller-identity --profile curso
  ```
  Para usar otro perfil, exporta `AWS_PROFILE` (scripts y Docker) y pon `perfil = "..."` en `terraform.tfvars`.
- Docker Desktop, Python 3.12, Terraform ≥ 1.6, AWS CLI v2 y VS Code.
- Dependencias de Python de los scripts de apoyo:

  ```bash
  # bash (macOS / Linux)
  python3 -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  ```
  ```powershell
  # PowerShell (Windows)
  py -3.12 -m venv .venv; .venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  ```

Todos los scripts de apoyo están en Python para que funcionen igual en Windows, macOS y Linux. Se ejecutan desde la raíz del repositorio.

## Estructura

```
├── comun/
│   ├── maestros.py           # datos maestros deterministas: 21 tiendas + 5 online, 4.000 clientes, 1.200 productos
│   ├── eventos.py            # construcción de eventos: generador y backfill
│   ├── referencia.py         # tipos de cambio y calendario
│   ├── athena.py, redshift.py, terraform.py   # utilidades de los scripts
├── infra/base/               # Terraform: bucket del lago + AWS Budgets (se mantiene entre sesiones)
├── demo1-ingesta/
│   ├── infra/                # Terraform: Firehose, IAM, alarma de DataFreshness
│   ├── api/                  # FastAPI + Dockerfile + tests
│   ├── generador/            # generador de ventas + Dockerfile + tests
│   ├── docker-compose.yml
│   ├── scripts/              # comprobar_bronze.py, evento_invalido.py, backfill_ventas.py
│   └── GUION.md
├── demo2-cdc-dms/
│   ├── infra/                # Terraform: VPC, RDS, Secrets Manager, DMS
│   ├── sql/                  # esquema, usuario DMS, cambios de la demo
│   ├── scripts/              # cargar_semilla.py, tarea_dms.py, aplicar_cambios.py, comprobar_cdc.py
│   └── GUION.md
├── demo3-catalogo-athena/
│   ├── infra/                # Terraform: bases de datos, crawler, workgroup
│   ├── sql/                  # bronze.ventas, exploración, Iceberg de prueba, bronze.clientes
│   ├── scripts/              # athena.py, comprobar_demo3.py
│   └── GUION.md
├── demo4-pipeline/
│   ├── infra/                # Terraform: Glue, red, Redshift, SNS, Step Functions, Scheduler, QuickSight
│   ├── infra-lakeformation/  # solo el profesor
│   ├── glue/                 # jobs, transformaciones.py y sus tests
│   ├── sql/                  # DDL de silver (Athena) y gold (Redshift)
│   ├── stepfunctions/        # plantilla de la máquina de estados y sus tests
│   ├── scripts/              # crear_silver, cargar_referencia, desplegar_redshift, ejecutar_pipeline...
│   ├── GUION.md
│   └── GUION_LAKE_FORMATION.md
├── demo5-api-fargate/
│   ├── infra/                # Terraform: red, roles y log group
│   ├── taskdef.json.tpl      # task definition; generar_taskdef.py escribe taskdef.json
│   ├── scripts/              # generar_taskdef, ip_tarea, comprobar_demo5, limpiar_demo5
│   └── GUION.md
├── demo6-prevision-sagemaker/
│   ├── infra/                # Terraform: red, dominio de Studio, rol, dataset de QuickSight
│   ├── sql/                  # UNLOAD, fct_prevision, v_prevision_vs_real
│   ├── notebooks/            # prevision_ventas.ipynb: autocontenido
│   ├── sagemaker/            # ruta opcional: entrenar.py, inferencia.py
│   ├── scripts/              # generar_clima, preparar_datos, cargar_prevision, comprobar_demo6, limpiar_demo6...
│   ├── requirements-opcional.txt   # SDK de SageMaker, en un entorno aparte
│   └── GUION.md
├── ejercicio-f-cognito/
│   ├── infra/                # Terraform: user pool, app client, grupo, API con mock y autorizador
│   ├── scripts/              # crear_usuario, probar_api
│   └── SOLUCION.md
└── ejercicio-g-guardduty-inspector/
    ├── infra/                # Terraform: detector, regla, SNS, Inspector para ECR, repositorio
    ├── scripts/              # estado_servicios, hallazgos_ejemplo, subir_imagenes, resumen_inspector
    └── SOLUCION.md
```

`comun/maestros.py` es la única fuente de tiendas, clientes y productos. El generador (demo 1) y la carga de RDS (demo 2) lo usan, así que cualquier `cliente_id` o `producto_id` de una venta existe en los maestros que replica DMS.

## Orden de ejecución

| Paso | Comando (desde la raíz) | Coste |
|---|---|---|
| 1. Base | `cd infra/base` → copia `terraform.tfvars.ejemplo` como `terraform.tfvars` y pon tu email → `terraform init && terraform apply` | Céntimos (S3) |
| 2. Demo 1: infraestructura | `cd demo1-ingesta/infra && terraform init && terraform apply` | Céntimos (por GB en Firehose) |
| 3. Demo 1 | Ver [demo1-ingesta/GUION.md](demo1-ingesta/GUION.md) | |
| 4. Demo 2: infraestructura | `cd demo2-cdc-dms/infra && terraform init && terraform apply` (≈ 10 min) | **≈ 0,06 USD/h** mientras exista |
| 5. Demo 2 | Ver [demo2-cdc-dms/GUION.md](demo2-cdc-dms/GUION.md) | |
| 6. Limpieza demo 2 | `python demo2-cdc-dms/scripts/tarea_dms.py parar` y `cd demo2-cdc-dms/infra && terraform destroy` | |
| 7. Histórico | `python demo1-ingesta/scripts/backfill_ventas.py` | Céntimos |
| 8. Demo 3 | Ver [demo3-catalogo-athena/GUION.md](demo3-catalogo-athena/GUION.md) | Céntimos |
| 9. Demo 4 | Ver [demo4-pipeline/GUION.md](demo4-pipeline/GUION.md) (la preparación tarda ~30 min) | Ver abajo |
| 10. Demo 5 | Ver [demo5-api-fargate/GUION.md](demo5-api-fargate/GUION.md). **Al acabar, a 0 tareas** | Céntimos |
| 11. Demo 6 | Ver [demo6-prevision-sagemaker/GUION.md](demo6-prevision-sagemaker/GUION.md). **Al acabar, space parado** | < 1 USD |
| 12. Ejercicio F | Ver [ejercicio-f-cognito/SOLUCION.md](ejercicio-f-cognito/SOLUCION.md) | Nivel gratuito |
| 13. Ejercicio G | Ver [ejercicio-g-guardduty-inspector/SOLUCION.md](ejercicio-g-guardduty-inspector/SOLUCION.md). **Se destruye al acabar** | Prueba gratuita |

La base y las demos 1, 3, 5 y 6 y el ejercicio F **se mantienen**: sin tareas ni space no tienen coste por hora. La demo 2 y el ejercicio G se **destruyen** al terminar.

**La demo 4 se mantiene para la sesión 3, y sí tiene un coste fijo pequeño.** El workgroup público de Redshift lleva una IP elástica (~0,005 USD/h, ~3,60 USD/mes) aunque no haya consultas, más ~0,80 USD/mes de dos secretos. Mientras consulta, Redshift cuesta ~1,50 USD/h, con un tope de 10 RPU-hora al día. La programación horaria está **desactivada** por defecto.

## Decisiones y avisos

- **Región** `eu-west-1`, configurable con la variable `region` de `infra/base`. Los demás módulos la leen de su estado.
- **Bucket** `retail-company-datalake-prod-<ID de cuenta>`. Los nombres de bucket son únicos en todo AWS, así que el sufijo por defecto es el ID de cuenta (variable `sufijo_bucket`). En las diapositivas aparece sin sufijo.
- **`force_destroy = true`** en el bucket: `terraform destroy` de la base borra el bucket **con todo su contenido y todas sus versiones**. Es un entorno de curso. En producción iría a `false`.
- **Estado de Terraform local**, uno por módulo y sin backend remoto. Los módulos de las demos leen los outputs de la base con `terraform_remote_state` (backend `local`). Por eso hay que aplicar la base primero y **no moverla de carpeta**.
- **Secretos.** El estado de la demo 2 contiene la contraseña maestra de RDS en claro. `.gitignore` excluye `*.tfstate*`, `terraform.tfvars`, `.env` y `salida/`. Nunca subas estos ficheros.
- **AWS Budgets** avisa por email al 80 % y al 100 % de 10 USD al mes. Es un aviso, no un límite: no para nada.
- **Etiquetas**: todos los recursos llevan `proyecto = curso-aws-hp`, `sesion = 1 | 2 | 3` y `demo = base | demo1 | demo2 | demo3 | demo4 | lakeformation | demo5 | demo6 | ejercicio-f | ejercicio-g`. Para listarlos:
  ```bash
  aws resourcegroupstaggingapi get-resources --tag-filters Key=proyecto,Values=curso-aws-hp --profile curso --region eu-west-1
  ```

## Credenciales dentro de Docker

El compose monta `~/.aws` en `/aws` en modo de solo lectura y usa el perfil `curso`. La imagen de la API no contiene credenciales: en la sesión 3, en ECS, las toma del task role.

**Windows (PowerShell).** `~/.aws` funciona en Docker Desktop. Para usar otro perfil: `$env:AWS_PROFILE="otro"; docker compose up --build -d`.

**IAM Identity Center (SSO).** boto3 lee el token de `~/.aws/sso/cache`, que está dentro del montaje. Haz antes `aws sso login --profile curso`. Si el token caduca durante la demo, la API responde 503 con el error de AWS: repite el login y reinicia la API con `docker compose restart api`.

**Linux con un usuario distinto de 1000** (`id -u` ≠ 1000). El contenedor corre como usuario 1000 y no puede leer `~/.aws` si los ficheros tienen permisos 600. La alternativa es pasar credenciales temporales en un `.env`:

```bash
cd demo1-ingesta
aws configure export-credentials --profile curso --format env-no-export > .env
```
```powershell
cd demo1-ingesta
aws configure export-credentials --profile curso --format env-no-export | Out-File -Encoding ascii .env
```

Después, en `docker-compose.yml`, comenta `AWS_PROFILE` y descomenta `env_file: .env` en el servicio `api`. Las credenciales temporales **caducan** (normalmente en 1–12 h) y hay que regenerarlas. `.env` está en `.gitignore`.

En Linux, crea también la carpeta de salida antes de arrancar (`mkdir -p salida && chmod 777 salida`) para que el generador, que corre como usuario 1000, pueda escribir `salida/resumen.json`. Si no puede, el resumen sale en el log.

**Permisos para enviar a Firehose.** Si tu usuario o rol no tiene permisos sobre Firehose, adjúntale la política `api-ventas-firehose-put` que crea la demo 1 (`terraform output politica_put_arn`):

```bash
aws iam attach-user-policy --user-name <tu-usuario> --policy-arn <arn> --profile curso
```

## Desarrollo

```bash
pip install -r requirements-dev.txt
pytest                      # tests sin AWS: Stubber, moto y PySpark local (necesita Java 8, 11 o 17)
ruff check .
terraform fmt -check -recursive && (cd infra/base && terraform validate)
```

`transformaciones.py` tiene tests locales con el PySpark de Glue 5.0 (Spark 3.5.4). El MERGE real sobre Iceberg, Data Quality y los bookmarks solo se prueban contra AWS.

Los tests incluyen también una prueba de extremo a extremo (generador → API → Firehose simulado con moto → S3 simulado) que comprueba que lo que llega a bronze cuadra con el resumen del generador.
