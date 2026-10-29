# Guion · Demo 1: del TPV a bronze

**Flujo:** generador → API de ventas (FastAPI en Docker) → Amazon Data Firehose `hp-retail-ventas` → S3 `bronze/ventas/anio=AAAA/mes=MM/dia=DD/`
**Duración:** ~25 min (10 de ellos con el generador en marcha mientras se explica).
**Antes de clase:** perfil `curso` operativo (`aws sts get-caller-identity --profile curso`), Docker Desktop arrancado, imágenes construidas una vez (`docker compose build`) y entorno de Python con `requirements.txt` activado.

Todos los comandos se lanzan desde la **raíz del repositorio**, salvo que se indique otra cosa.

---

## 1. Crear la infraestructura (≈ 2 min)

Se crean el bucket, el stream de Firehose y el rol IAM. La base se crea una vez y se mantiene entre sesiones.

```bash
cd infra/base
cp terraform.tfvars.ejemplo terraform.tfvars        # PowerShell: Copy-Item terraform.tfvars.ejemplo terraform.tfvars
# editar terraform.tfvars: email_alertas = "..."
terraform init && terraform apply
cd ../../demo1-ingesta/infra
terraform init && terraform apply
cd ../..
```

**Salida esperada:** `Apply complete! Resources: 6 added` (base) y `Resources: 9 added` (demo 1), y después los outputs:

```
bucket_name = "retail-company-datalake-prod-123456789012"
stream_name = "hp-retail-ventas"
```

Llegarán dos emails: la confirmación de la suscripción SNS de la alarma (hay que pulsar *Confirm subscription*) y nada más hasta que salte el presupuesto.

**Qué contar:** prefijo con la fecha de **llegada** (`!{timestamp}`), no la de negocio; buffer de 30 s o 5 MiB; GZIP con extensión `.json.gz`; sin Lambda ni conversión de formato, porque bronze es una copia fiel.

**Si falla:**
- `BucketAlreadyExists`: el sufijo ya está en uso. Pon `sufijo_bucket = "algo-unico"` en `infra/base/terraform.tfvars`.
- `Unable to find remote state` en la demo 1: falta aplicar `infra/base`.
- `EntityAlreadyExists` en `api-ventas-firehose-put`: la política ya existe en la cuenta de otra ejecución. Impórtala (`terraform import aws_iam_policy.api_put <arn>`) o bórrala si es tuya.

## 2. Levantar la API y el generador (≈ 1 min)

```bash
cd demo1-ingesta
docker compose up --build -d
docker compose ps
```

**Salida esperada:** `api` en estado `healthy` y `generador` en `running`. La documentación de la API está en <http://localhost:8000/docs>.

**Si falla:**
- La API se reinicia con `RuntimeError: Falta la región`: falta `AWS_REGION` en el compose.
- `ProfileNotFound: The config profile (curso) could not be found`: el perfil no existe en `~/.aws`. Para otro perfil: `AWS_PROFILE=otro docker compose up -d` (PowerShell: `$env:AWS_PROFILE="otro"; docker compose up -d`).
- Linux con un usuario distinto de 1000, o SSO que no funciona: usa la alternativa del `.env` (ver README).

## 3. Generar 10 minutos de ventas en hora pico (≈ 10 min, en segundo plano)

```bash
MODO=pico docker compose up -d generador            # 10 eventos/s durante 10 min
docker compose logs -f generador
```
```powershell
$env:MODO="pico"; docker compose up -d generador
docker compose logs -f generador
```

**Salida esperada (cada 10 s):**

```
INFO generador: Progreso   60 s: 601 generados, 601 enviados, 601 aceptados, 0 duplicados, 0 inválidos rechazados, 0 perdidos (10.0 ev/s)
```

y en la API (`docker compose logs api`): `Lote recibido: 11 registros, 11 enviados, 0 reintentos`.

Al terminar escribe `demo1-ingesta/salida/resumen.json`. `Ctrl+C` solo sale de los logs: el generador sigue en marcha.

**Variantes:** `DURACION_MIN=2` para una ejecución corta. `DUPLICADOS_PCT=5` reenvía un 5 % de los eventos con el mismo `event_id` (sirve en la sesión 2 para enseñar a desduplicar). `INVALIDOS_PCT=2` envía eventos inválidos, que la API debe rechazar con 422.

**Si falla:**
- `La API respondió 503: Error enviando a Firehose: … ExpiredToken`: las credenciales han caducado. Haz `aws sso login --profile curso` (o regenera el `.env`) y luego `docker compose restart api`.
- `AccessDeniedException … firehose:PutRecordBatch`: adjunta la política `api-ventas-firehose-put` a tu usuario (ver README).

## 4. Seguir las métricas del stream en CloudWatch (≈ 3 min)

Consola: **Amazon Data Firehose → hp-retail-ventas → Monitoring**. Las métricas tardan 1–2 minutos en aparecer.

- `IncomingRecords` / `IncomingBytes`: ~600 registros por minuto en hora pico.
- `DeliveryToS3.Records`: lo entregado a S3.
- `DeliveryToS3.DataFreshness`: antigüedad del registro más antiguo pendiente. Debe quedar por debajo de 60 s con el buffer de 30 s. Si supera 120 s durante 2 minutos, salta la alarma `hp-retail-ventas-data-freshness`.

Desde la terminal:

```bash
aws cloudwatch describe-alarms --alarm-names hp-retail-ventas-data-freshness --query "MetricAlarms[0].StateValue" --profile curso --region eu-west-1
```

## 5. Explorar bronze en S3: un fichero gzip cada 30 s con JSON Lines (≈ 4 min)

```bash
BUCKET=$(terraform -chdir=infra/base output -raw bucket_name)
aws s3 ls s3://$BUCKET/bronze/ventas/ --recursive --profile curso | tail -5
FICHERO=$(aws s3 ls s3://$BUCKET/bronze/ventas/ --recursive --profile curso | tail -1 | awk '{print $4}')
aws s3 cp s3://$BUCKET/$FICHERO - --profile curso | gunzip | head -3 | jq .
```
```powershell
$BUCKET = terraform -chdir=infra/base output -raw bucket_name
aws s3 ls s3://$BUCKET/bronze/ventas/ --recursive --profile curso | Select-Object -Last 5
```

En Windows (y en general), el script hace lo mismo sin `gunzip`, `head` ni `jq`, y además revisa los criterios de aceptación:

```bash
python demo1-ingesta/scripts/comprobar_bronze.py          # --fecha 2026-10-24 para otro día
```

**Salida esperada:**

```
2026-10-28 17:09:12   31245 bronze/ventas/anio=2026/mes=10/dia=28/hp-retail-ventas-1-2026-10-28-17-08-40-<uuid>.json.gz
...
Criterios de aceptación
  [OK] Estructura anio=/mes=/dia= con ficheros .json.gz en JSON Lines  (21 ficheros)
  [OK] Líneas en bronze = eventos aceptados por la API  (6012 líneas / 6012 aceptados; ...)
  [OK] Un fichero nuevo cada ~30 s  (mediana 30 s entre 21 ficheros)
  [OK] Nada en errors/ (salvo pruebas provocadas)  (0 ficheros)
  [OK] DataFreshness por debajo de 2 minutos  (máximo 48 s)
```

**Qué contar:** la carpeta es la fecha de **llegada**. Un evento con `event_ts` de las 23:59:59 puede caer en la carpeta del día siguiente. Los ficheros llevan `.json.gz` porque Athena decide si descomprime por la extensión, y lo necesitaremos en la sesión 2.

**Si falla:** «Líneas en bronze ≠ aceptados» justo al terminar: espera 30–60 s (el último buffer todavía no se ha entregado) y repite.

**Pregunta habitual: «el `.json.gz` no está comprimido».** Si se descarga con el botón *Download* de la consola de S3, el navegador lo guarda ya descomprimido, aunque mantiene el nombre `.json.gz`. Firehose marca los objetos con `Content-Encoding: gzip` y el navegador lo trata como una compresión de transporte. En S3 el objeto sí está en gzip, como se ve con `aws s3api head-object` (`ContentEncoding: gzip`) o descargándolo con `aws s3 cp` (empieza por los bytes `1f 8b`). Athena, Glue y `aws s3 cp` leen los bytes tal cual, así que no les afecta.

## 6. Enviar un evento inválido y ver el 422 (≈ 2 min)

```bash
curl -s -X POST localhost:8000/ventas/lote \
  -H 'Content-Type: application/json' \
  -d '[{"event_id": "no-es-uuid"}]' | jq '.detail[0]'
```

Multiplataforma (incluido Windows):

```bash
python demo1-ingesta/scripts/evento_invalido.py
python demo1-ingesta/scripts/evento_invalido.py --campo unidades     # evento completo con unidades = 0
```

**Salida esperada:**

```json
{
  "type": "uuid_parsing",
  "loc": ["body", 0, "event_id"],
  "msg": "Input should be a valid UUID, invalid character: found `n` at 0",
  "input": "no-es-uuid"
}
```

**Qué contar:** el contrato se valida en la entrada, así que a bronze solo llega lo que lo cumple. Un lote de más de 500 eventos también devuelve 422 (`too_long`). Si Firehose falla tras 5 intentos, la API responde 503 con los registros pendientes.

---

## Limpieza (checklist de la diapositiva)

```bash
cd demo1-ingesta
docker compose down
```

- [x] `docker compose down`.
- [x] **Firehose y bucket se mantienen** para la sesión 2: no tienen coste por hora, solo por GB ingerido o almacenado.
- No hagas `terraform destroy` de `infra/base` ni de `demo1-ingesta/infra` hasta terminar el curso. Si lo haces, `force_destroy` borra el bucket con todos los datos.
