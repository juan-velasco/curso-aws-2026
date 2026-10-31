# Guion · Demo 3: catálogo y Athena sobre bronze

**Flujo:** S3 `bronze/` → Glue Data Catalog (DDL con partition projection y crawler) → Athena (workgroup `curso`)
**Duración:** ~20 min.
**Coste:** céntimos. En las pruebas, 11 MB por una consulta sin filtro (≈ 0,00005 USD) y 150 KB con filtro de partición.

Todos los comandos se lanzan desde la **raíz del repositorio**.

---

## Antes de clase

### Infraestructura (≈ 1 min)

```bash
cd demo3-catalogo-athena/infra
terraform init && terraform apply     # 7 recursos: bases de datos bronze y silver, crawler y su rol, workgroup curso
cd ../..
```

### Datos

```bash
python demo1-ingesta/scripts/backfill_ventas.py                 # 120 días hasta ayer: ~260.000 eventos, ~1 min
cd demo1-ingesta
MODO=pico DUPLICADOS_PCT=5 docker compose up --build -d         # 10 min en hora pico con duplicados
cd ..
```
```powershell
python demo1-ingesta/scripts/backfill_ventas.py
cd demo1-ingesta
$env:MODO="pico"; $env:DUPLICADOS_PCT="5"; docker compose up --build -d
cd ..
```

**Salida esperada del backfill:** `Días escritos: 120 (0 ya estaban). Eventos: 260462. Ficheros: 185.` Con otra fecha de `--hasta` cambian los números. Repetirlo no duplica nada: salta los días que ya tienen ficheros `backfill-`.

---

## 1. Revisar las bases de datos `bronze` y `silver` en Glue Data Catalog (≈ 2 min)

Terraform ya ha creado `bronze` y `silver`. Consola: **AWS Glue → Data Catalog → Databases**.

**Qué contar:** una base de datos del catálogo es solo metadatos, no contiene datos. Desde la consola se crearía con *Add database*; desde Athena, con `CREATE DATABASE bronze`.

## 2. Lanzar el crawler de productos y crear `bronze.clientes` con DDL (≈ 3 min)

```bash
aws glue start-crawler --name curso-bronze-cdc --profile curso --region eu-west-1
aws glue get-crawler --name curso-bronze-cdc --query "Crawler.[State,LastCrawl.Status]" --profile curso --region eu-west-1
```

Tarda ~1 min. **Salida esperada:** `READY`, `SUCCEEDED` y la tabla `bronze.productos`, con `precio_catalogo` y `coste_unitario` en `decimal(8,2)` y `ts_commit` en `string`.

**Qué contar: el crawler no es magia.** Este crawler solo rastrea `productos`, a propósito. En `clientes`, DMS deja la carga completa en la raíz de la carpeta, sin `Op`, y los cambios en `AAAA/MM/DD/`, con `Op`. Con esa mezcla el crawler crea una tabla por fichero (`load00000001_parquet`, `2026`) y deja en su log `Found schemas don't match ... Can not create Tables`. Por eso `clientes` se crea con DDL:

```bash
python demo3-catalogo-athena/scripts/athena.py --fichero demo3-catalogo-athena/sql/04_bronze_clientes.sql
python demo3-catalogo-athena/scripts/athena.py --sql "SELECT op, count(*) AS n FROM bronze.clientes GROUP BY 1 ORDER BY 1"
```

**Salida esperada:** 4.000 filas con `op` vacío (carga completa) y una con `D`, otra con `I` y otra con `U`. Son 4.003 filas: bronze guarda la historia. El estado actual de cada cliente lo calcula silver en la demo 4.

## 3. Crear `bronze.ventas` con partition projection desde el editor de Athena (≈ 4 min)

Pega `sql/01_bronze_ventas.sql` en el editor de Athena con el nombre real del bucket en lugar de `${bucket}`, o lánzalo desde la terminal:

```bash
python demo3-catalogo-athena/scripts/athena.py --fichero demo3-catalogo-athena/sql/01_bronze_ventas.sql
```

**Qué contar:** con partition projection, Athena calcula las particiones a partir del `WHERE`, sin crawler ni `MSCK REPAIR`. Solo sirve en Athena: Glue y Redshift Spectrum no la usan, y por eso los Glue Jobs de la demo 4 leen directamente de S3. Las particiones son la fecha de **llegada** en UTC, no la de negocio.

## 4. Usar el workgroup `curso` (≈ 2 min)

Terraform ya lo ha creado. Consola: **Athena → Workgroups → curso**: resultados en `athena-results/` con SSE-S3, configuración forzada, **límite de 10 GB escaneados por consulta** y métricas en CloudWatch. En el editor de Athena, selecciona `curso` arriba a la derecha. `athena.py` ya lo usa.

**Qué contar:** desde la consola se crearía con *Create workgroup*. El límite es la red de seguridad: una consulta sin filtro sobre un lago grande se corta antes de costar dinero.

## 5. Lanzar las consultas de exploración y revisar duplicados (≈ 5 min)

```bash
python demo3-catalogo-athena/scripts/athena.py --fichero demo3-catalogo-athena/sql/02_exploracion.sql --fecha 2026-10-28
```

**Salida esperada** (el día 28 tiene backfill y Firehose):

```
  eventos  unicos
  3395     3364
  Datos escaneados: 148.67 KB (≈ 0.000001 USD)
```

**Qué contar:**
- **Duplicados:** `count(*) > count(DISTINCT event_id)`. Bronze es una copia fiel; desduplicar es tarea de silver.
- **Monedas:** el «top 5 por venta neta» suma importes en moneda local, así que los productos con ventas en JPY salen arriba. Es un error instructivo de consultar bronze directamente: silver lo pasa todo a EUR.

## 6. Comparar los bytes escaneados con y sin filtro de partición (≈ 3 min)

```bash
python demo3-catalogo-athena/scripts/athena.py --sql "SELECT count(*) AS eventos FROM bronze.ventas WHERE anio = '2026' AND mes = '10' AND dia = '28'"
python demo3-catalogo-athena/scripts/athena.py --sql "SELECT count(*) AS eventos FROM bronze.ventas"
```

**Salida esperada:** con filtro, 148,67 KB; sin filtro, unos 11 MB. En la consola, es el dato **Data scanned** de cada consulta.

**Qué contar:** se paga por datos escaneados (5 USD/TB). Filtrar por partición escanea unas 75 veces menos, y la diferencia crece con el histórico.

## Extra: Iceberg desde Athena (≈ 4 min, opcional)

Si sobra tiempo, o como enlace con la demo 4:

```bash
python demo3-catalogo-athena/scripts/athena.py --fichero demo3-catalogo-athena/sql/03_iceberg_prueba.sql
```

**Salida esperada:** `filas_ahora` = 3 y `filas_hace_5_s` = 2 (el time travel no ve la última escritura), `OPTIMIZE` y `VACUUM` sin error y la tabla borrada al final.

La diapositiva consulta «hace una hora». Aquí son 5 segundos porque la tabla es recién creada; el script deja pasar ese tiempo solo por lo que tarda cada sentencia. Si `filas_hace_5_s` sale 3, Athena ha tardado menos en el último `INSERT`: repite el fichero.

---

## Comprobación final

```bash
python demo3-catalogo-athena/scripts/comprobar_demo3.py --fecha 2026-10-28
```

**Salida esperada:**

```
Criterios de aceptación
  [OK] Existe bronze.ventas
  [OK] bronze.clientes con los tipos de DMS
  [OK] bronze.productos con los tipos de DMS
  [OK] Athena lee los .json.gz: recuento de 2026-10-28 = líneas en S3  (3395 en Athena / 3395 en S3)
  [OK] Duplicados visibles: count(*) > count(DISTINCT event_id)  (3395 eventos, 3364 únicos)
  [OK] Filtrar por partición escanea mucho menos  (148.67 KB frente a 11.01 MB)
  [OK] bronze.clientes se puede consultar  (4003 filas)
  [OK] bronze.productos se puede consultar  (1200 filas)
```

## Si algo falla

- **`Unable to find remote state`:** falta aplicar `infra/base`.
- **`TABLE_NOT_FOUND` en `bronze.clientes`:** ejecuta `sql/04_bronze_clientes.sql`. En `bronze.productos`: lanza el crawler.
- **El recuento de Athena no cuadra con S3 justo después del generador:** espera 30–60 s, porque el último buffer de Firehose aún no se ha entregado.
- **`Query exhausted` o error de límite:** el workgroup corta las consultas de más de 10 GB. Con estos datos no debería pasar.
- **La consola muestra `.json.gz` «sin comprimir» al descargar:** es el navegador, por `Content-Encoding: gzip` (ver el guion de la demo 1). Athena lo lee bien.

## Limpieza

Nada que apagar: Athena y el catálogo no tienen coste por hora. Los resultados de `athena-results/` caducan a los 7 días. **Se mantiene todo** para la demo 4.
