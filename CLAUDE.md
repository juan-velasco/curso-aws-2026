# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es

Demos y ejercicios de un curso de AWS: un retail de moda cuyas ventas alimentan un lago en S3 con arquitectura medallón (bronze, silver, gold). Cada demo tiene un `GUION.md` y cada ejercicio un `SOLUCION.md` que el profesor sigue literalmente en clase, así que **un comando de esos ficheros forma parte del producto**: si cambia el código, hay que cambiar también el guion.

La documentación, los mensajes y los comentarios van en español.

## Comandos

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt

pytest                                                   # sin AWS: Stubber, moto y PySpark local (necesita Java 8, 11 o 17)
pytest demo1-ingesta/api/tests/test_api.py -k lote_vacio # un solo test
ruff check .
terraform fmt -check -recursive
terraform -chdir=infra/base validate                     # requiere `terraform init` en ese módulo; repetir en cada módulo tocado
```

Para ejecutar contra AWS, en cada terminal nueva (en `eu-west-1`, con el perfil que corresponda):

```bash
export AWS_PROFILE=default AWS_REGION=eu-west-1 TF_VAR_perfil=default
```

Sin `AWS_PROFILE` ni `TF_VAR_perfil`, scripts, Docker y Terraform buscan un perfil `curso`, que no existe en el equipo del profesor. Sin `AWS_REGION`, algunos comandos actúan en la región del perfil, que aquí es `eu-west-3`.

Los scripts se lanzan desde la raíz: `python demo4-pipeline/scripts/comprobar_demo4.py`. Los comprobadores `comprobar_*.py` de cada demo son la verificación contra AWS; la lista está en `docs/REFERENCIA.md`.

## Restricciones

- **Pregunta antes de crear, modificar o borrar recursos en AWS**: `terraform apply` y `destroy`, `limpiar_*.py`, `create-*`, lanzar el pipeline o el generador. Son seguros `terraform plan`, las llamadas `describe`, `get` y `list`, y los comprobadores. Las consultas de Athena guardan resultados en `athena-results/` y cuestan céntimos.
- **El repositorio es público.** Nada de ID de cuenta ni emails en lo versionado: el bucket se escribe `retail-company-datalake-prod-<ID de cuenta>`. Quedan fuera de git `*.tfstate*` (el de la demo 2 lleva la contraseña de RDS en claro), `terraform.tfvars`, `.env`, `salida/` y `demo5-api-fargate/taskdef.json`.

## Arquitectura

**Módulos de Terraform encadenados.** Cada `infra/` tiene estado local, sin backend remoto. Los módulos leen a los anteriores con `terraform_remote_state` y los scripts con `comun/terraform.py` (`outputs("demo1-ingesta/infra")`), por lo que `infra/base` se aplica primero y no se puede mover de carpeta. La región solo se define en la base.

**Datos compartidos.** `comun/maestros.py` es la única fuente, determinista, de tiendas, clientes y productos. Lo usan el generador, el backfill y la carga de RDS, y así todo `cliente_id` y `producto_id` de una venta existe en lo que replica DMS. Las cifras de los guiones dependen de esas semillas.

**Las demos dependen de los datos de las anteriores:**

1. Demo 1: generador → API FastAPI → Firehose → `bronze/ventas/`. La API valida y reenvía cada lote en una sola llamada `PutRecordBatch`, sin acumular: agrupan el generador (antes) y Firehose (después).
2. Demo 2: RDS → DMS → `bronze/cdc/`. Se destruye al acabar, pero sus ficheros siguen. **Repetirla altera las cifras de las demos 3 y 4.**
3. Demo 3: catálogo de Glue y Athena. Necesita la demo 2 para `bronze.productos` y `bronze.clientes`.
4. Demo 4: Glue → silver (Iceberg) → gold (Redshift) → QuickSight, orquestado con Step Functions.
5. Demo 5: la misma imagen de la API de la demo 1, en Fargate. ECR, cluster y service se crean por CLI, **fuera de Terraform**; los borra `limpiar_demo5.py --todo`.
6. Demo 6: gold → UNLOAD → notebook → `gold.fct_prevision`.

Los ejercicios F y G solo dependen de la base.

**Detalles que no se ven en un solo fichero:**

- Las particiones `anio=/mes=/dia=` de bronze son la fecha de **llegada** a Firehose, no `event_ts`. En el histórico, la del evento.
- Glue lee `bronze/ventas` directamente de S3 con bookmarks, porque partition projection solo funciona en Athena.
- Terraform sube los scripts de `demo4-pipeline/glue/` a S3 y `transformaciones.py` llega como `--extra-py-files`. Terraform también renderiza `stepfunctions/pipeline.asl.json` con `templatefile`. **Cambiar cualquiera de ellos no surte efecto hasta aplicar.**
- Glue 5.0 corre Python 3.11, no 3.12: `demo4-pipeline/glue/` no puede usar sintaxis exclusiva de 3.12.
- El notebook de la demo 6 es autocontenido, y el SDK `sagemaker` va en un entorno aparte (`requirements-opcional.txt`).
- Los security groups de las demos 2, 4 y 5 admiten la IP detectada al aplicar: al cambiar de red hay que aplicar de nuevo.

## Convenciones

- **Módulo o carpeta de tests nuevos:** añade la carpeta a `pythonpath` y `testpaths` en `pyproject.toml`, y el módulo a `known-first-party` de ruff si se importa. Los tests usan `--import-mode=importlib`.
- **Scripts que importan `comun`:** insertan la raíz en `sys.path` al principio, para funcionar desde cualquier carpeta. Solo Python en los scripts de apoyo: deben funcionar igual en Windows, macOS y Linux.
- **Guiones con comandos de shell:** bloque de bash y bloque de PowerShell cuando difieran.
- **Dependencias:** con versión fijada en el `requirements` que corresponda. La imagen del generador se construye desde la raíz (`context: ..`) para copiar `comun/`.
- **Recursos nuevos:** etiquetas `proyecto = curso-aws-hp`, `sesion` y `demo`. Un coste fijo nuevo se apunta en `docs/ESTADO.md`.

## Documentación

- `docs/ESTADO.md`: lo desplegado, costes, pendientes y **qué falta por demostrar**. Actualízalo al cambiar el despliegue.
- `docs/REFERENCIA.md`: rutas en S3, esquemas, roles y decisiones de diseño. Consúltalo antes de cambiar algo que parezca raro: puede ser una decisión tomada.
- `docs/CAMBIOS_DIAPOSITIVAS.md`: diferencias entre las diapositivas, que están fuera del repositorio, y lo que funciona al probarlo. Si un cambio deja una diapositiva desfasada, apúntalo aquí.
