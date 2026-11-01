# Guion · Demo 5: la API de ventas en ECS con Fargate

**Flujo:** imagen de la API en ECR → task definition → service en Fargate con IP pública → generador → Firehose → `bronze/ventas/`.
**Duración:** ~30 min, 3 a 10 de ellos con el generador en marcha.
**Coste:** céntimos. Fargate ARM64 con 0,25 vCPU y 0,5 GB cuesta unos 0,01 USD/h (estimación, sin factura); 30 minutos, menos de 1 céntimo, más CloudWatch Logs y Firehose. La imagen ocupa 71 MB en ECR, ~0,01 USD/mes. **Sin tareas, no hay coste de cómputo.**

Todos los comandos se lanzan desde la **raíz del repositorio**. Requisitos: `infra/base` y `demo1-ingesta/infra` aplicados, y Docker con `buildx`.

---

## Antes de clase

```bash
cd demo5-api-fargate/infra
terraform init && terraform apply     # 13 recursos: red, security group, 2 roles y log group
cd ../..
python demo5-api-fargate/scripts/generar_taskdef.py
```

**Salida esperada:** `Escrito demo5-api-fargate/taskdef.json`. Lleva el ID de cuenta y no se sube a git.

El security group solo deja entrar a la IP desde la que aplicas. **Si cambias de red, repite `terraform apply`.**

Para los comandos de abajo:

```bash
export CUENTA=$(terraform -chdir=demo5-api-fargate/infra output -raw account_id)
export SUBNET=$(terraform -chdir=demo5-api-fargate/infra output -json subredes | python -c "import json,sys; print(','.join(json.load(sys.stdin)))")
export SG=$(terraform -chdir=demo5-api-fargate/infra output -raw security_group)
```
```powershell
$env:CUENTA = terraform -chdir=demo5-api-fargate/infra output -raw account_id
$env:SUBNET = (terraform -chdir=demo5-api-fargate/infra output -json subredes | ConvertFrom-Json) -join ","
$env:SG = terraform -chdir=demo5-api-fargate/infra output -raw security_group
```

---

## 1. Crear el repositorio en ECR y subir la imagen para ARM64 (≈ 5 min)

El contexto de build es `demo1-ingesta/api/`, no la raíz.

```bash
aws ecr create-repository --repository-name api-ventas --image-scanning-configuration scanOnPush=true
aws ecr get-login-password | docker login --username AWS --password-stdin $CUENTA.dkr.ecr.eu-west-1.amazonaws.com
cd demo1-ingesta/api
docker buildx build --platform linux/arm64 --push -t $CUENTA.dkr.ecr.eu-west-1.amazonaws.com/api-ventas:1.0.0 .
cd ../..
```
```powershell
aws ecr create-repository --repository-name api-ventas --image-scanning-configuration scanOnPush=true
aws ecr get-login-password | docker login --username AWS --password-stdin "$env:CUENTA.dkr.ecr.eu-west-1.amazonaws.com"
cd demo1-ingesta/api
docker buildx build --platform linux/arm64 --push -t "$env:CUENTA.dkr.ecr.eu-west-1.amazonaws.com/api-ventas:1.0.0" .
cd ../..
```

**Qué contar:** ARM64 cuesta menos en Fargate. En un Mac con Apple Silicon, el build es nativo. En un portátil x86, Docker Desktop lo emula con QEMU y tarda más: **no se ha podido probar**, porque el equipo de pruebas es ARM. Lleva la imagen subida antes de clase si tu portátil es x86.

En ECR, abre el escaneo de la imagen: el básico de `scanOnPush` encontró 5 de severidad alta, 10 medias y 3 bajas. El ejercicio G vuelve sobre esto.

## 2. Revisar el task role (≈ 3 min)

Terraform ya lo ha creado. Consola: **IAM → Roles → api-ventas-task**.

**Qué contar:**
- **Permisos:** solo la política `api-ventas-firehose-put`, con `PutRecord` y `PutRecordBatch` sobre un único stream.
- **Confianza:** `ecs-tasks.amazonaws.com`, con la condición `aws:SourceAccount`.
- **Dos roles distintos:** el *execution role* (`curso-aws-hp-ecs-ejecucion`) lo usa ECS para descargar la imagen y escribir los logs. El *task role* lo usa tu código. No se usa `ecsTaskExecutionRole`, porque en una cuenta de empresa puede ser compartido.

## 3. Registrar la task definition y crear cluster y service (≈ 5 min)

```bash
aws ecs create-cluster --cluster-name hp-retail
aws ecs register-task-definition --cli-input-json file://demo5-api-fargate/taskdef.json
aws ecs create-service --cluster hp-retail --service-name api-ventas \
  --task-definition api-ventas --desired-count 1 --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET],securityGroups=[$SG],assignPublicIp=ENABLED}"
aws ecs wait services-stable --cluster hp-retail --services api-ventas
```
```powershell
aws ecs create-cluster --cluster-name hp-retail
aws ecs register-task-definition --cli-input-json file://demo5-api-fargate/taskdef.json
aws ecs create-service --cluster hp-retail --service-name api-ventas `
  --task-definition api-ventas --desired-count 1 --launch-type FARGATE `
  --network-configuration "awsvpcConfiguration={subnets=[$env:SUBNET],securityGroups=[$env:SG],assignPublicIp=ENABLED}"
aws ecs wait services-stable --cluster hp-retail --services api-ventas
```

La tarea tarda ~45 s en estar en marcha. **Si es la primera vez que la cuenta usa ECS**, `create-service` puede fallar con `Unable to assume the service linked role`: AWS acaba de crear el rol `AWSServiceRoleForECS` y aún no está disponible. Espera 30 s y repite.

**Qué contar:** en `taskdef.json`, `AWS_REGION` es imprescindible: la API no arranca sin ella. Sin balanceador, cada tarea nueva cambia de IP: para esta demo vale, para producción no.

## 4. Obtener la IP pública y apuntar el generador (≈ 5 min)

```bash
python demo5-api-fargate/scripts/ip_tarea.py
curl http://<ip>:8000/health
cd demo1-ingesta
MODO=pico DURACION_MIN=3 docker compose run --rm --no-deps -e API_URL=http://<ip>:8000 generador
cd ..
```
```powershell
python demo5-api-fargate/scripts/ip_tarea.py
curl.exe http://<ip>:8000/health
cd demo1-ingesta
$env:MODO="pico"; $env:DURACION_MIN="3"; docker compose run --rm --no-deps -e API_URL=http://<ip>:8000 generador
cd ..
```

**Salida esperada:** `{"status":"ok"}` y, al cabo de 3 min, `1800 generados, 1800 enviados, 1800 aceptados, 0 perdidos`.

`--no-deps` evita levantar la API local: ahora la API está en Fargate. El generador corre en tu equipo; solo la API está en AWS.

## 5. Ver los logs en CloudWatch y los datos nuevos en bronze (≈ 5 min)

Espera ~1 min a que Firehose entregue el último buffer.

```bash
aws logs tail /ecs/api-ventas --since 10m
python demo5-api-fargate/scripts/comprobar_demo5.py
```

**Salida esperada:**

```
Criterios de aceptación
  [OK] Tarea en estado RUNNING
  [OK] /health responde desde este equipo  (HTTP 200)
  [OK] Logs recientes en /ecs/api-ventas  (api/api/...)
  [OK] Ficheros nuevos en bronze/ventas  (7 desde 12:13:31 UTC)
  [OK] Sin claves AWS en la task definition
  [OK] Las credenciales vienen del task role  (api-ventas-task)
```

**Qué contar:** la API es la misma imagen de la sesión 1, sin cambiar una línea. En Docker necesitaba tu `~/.aws`; aquí, ninguna clave: las credenciales vienen del task role.

**Los datos los procesa la demo 4 sin cambios:** `python demo4-pipeline/scripts/ejecutar_pipeline.py`. En la prueba, `silver.ventas` y `gold.fct_ventas` pasaron de 266.780 a 268.580 filas: justo los 1.800 eventos.

## 6. Bajar el servicio a 0 tareas (≈ 1 min)

```bash
aws ecs update-service --cluster hp-retail --service api-ventas --desired-count 0
python demo5-api-fargate/scripts/comprobar_demo5.py --parado
```

`limpiar_demo5.py` hace lo mismo y espera a que no quede ninguna tarea. **Salida esperada:** `[OK] Service con desired-count 0` y `[OK] Ninguna tarea en marcha`, ~30 s después.

---

## Si algo falla

- **`/health` no responde:** el security group solo admite la IP con la que aplicaste. Si has cambiado de red, repite `terraform apply`.
- **La tarea se para al arrancar, con `Falta la región de AWS`:** falta `AWS_REGION` en la task definition.
- **`CannotPullContainerError`:** la imagen no está en ECR, o la subred no sale a internet: revisa `assignPublicIp=ENABLED`.
- **`exec format error`:** la imagen no es ARM64. Repite el build con `--platform linux/arm64`.
- **`ip_tarea.py` dice que no hay tarea:** espera un minuto, o mira los eventos del service en la consola.
- **`Ficheros nuevos` en FALLO:** Firehose entrega cada ~30 s. Espera un minuto.

## Limpieza

```bash
python demo5-api-fargate/scripts/limpiar_demo5.py          # a 0 tareas: basta entre clases
python demo5-api-fargate/scripts/limpiar_demo5.py --todo   # borra service, cluster, revisiones y repositorio
cd demo5-api-fargate/infra && terraform destroy && cd ../..
```

**El ejercicio G usa la imagen de `api-ventas`:** `--todo` lo avisa y pregunta antes de borrar el repositorio. El rol `AWSServiceRoleForECS` lo crea AWS y se queda en la cuenta, sin coste.
