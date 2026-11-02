# Guion · Demo 4: el pipeline de punta a punta

**Flujo:** bronze → Glue Jobs (silver en Iceberg, SCD2, Data Quality) → Redshift Serverless (gold) → QuickSight, orquestado con Step Functions.
**Duración:** ~40 min en clase, 11 de ellos con el generador en marcha. La preparación tarda ~30 min y **se hace antes de clase**: crear el workgroup y el primer job llevan varios minutos.

**En cada terminal nueva:** define el perfil y la región ([cómo](../README.md#preparar-la-terminal)). Todos los comandos se lanzan desde la **raíz del repositorio**. Requisito: demo 3 aplicada y `bronze.ventas` creada.

---

## Preparación antes de clase

| Paso | Comando | Tiempo |
|---|---|---|
| 1. Variables | `cd demo4-pipeline/infra`, copia `terraform.tfvars.ejemplo` como `terraform.tfvars` y pon tu email | |
| 2. Infraestructura | `terraform init && terraform apply`, y vuelve a la raíz. **Confirma el correo de SNS** | ~5 min |
| 3. Tablas de silver | `python demo4-pipeline/scripts/crear_silver.py` | 1 min |
| 4. Referencia | `python demo4-pipeline/scripts/cargar_referencia.py` | 2 min |
| 5. Gold | `python demo4-pipeline/scripts/desplegar_redshift.py` | 2 min |
| 6. Datos | Backfill y generador `MODO=pico DUPLICADOS_PCT=5` (ver el guion de la demo 3) | 10 min |
| 7. Primera ejecución | `python demo4-pipeline/scripts/ejecutar_pipeline.py` | ~5 min |
| 8. Gold completo | `python demo4-pipeline/scripts/cargar_gold_inicial.py` | ~1 min |
| 9. QuickSight | Suscripción, `quicksight_activo = true` y `terraform apply` (ver [QuickSight](#quicksight-del-dataset-al-dashboard)) | 15 min |

**Salida esperada del paso 8:** `gold.fct_ventas: <n> filas`, el mismo número que `silver.ventas`. La máquina de estados solo recarga ayer y hoy, y por eso hace falta esta carga inicial.

Comprueba el resultado:

```bash
python demo4-pipeline/scripts/comprobar_demo4.py
```

**Coste de la preparación:** ver [Costes](#costes).

---

## 1. Lanzar el generador durante 10 minutos en hora pico (≈ 11 min, mientras se explica)

```bash
cd demo1-ingesta
MODO=pico DUPLICADOS_PCT=5 docker compose up -d     # 10 min por defecto
docker compose logs -f generador
cd ..
```
```powershell
cd demo1-ingesta
$env:MODO="pico"; $env:DUPLICADOS_PCT="5"; docker compose up -d
docker compose logs -f generador
cd ..
```

**Salida esperada:** ~6.000 eventos generados y ~300 duplicados en `demo1-ingesta/salida/resumen.json`. `Ctrl+C` solo sale de los logs.

**Qué contar:** los datos nuevos llegan a bronze con duplicados. Los bookmarks harán que el pipeline solo lea estos ficheros. Aprovecha estos minutos para repasar la arquitectura.

## 2. Ejecutar la máquina de estados manualmente y seguir el grafo (≈ 5 min)

Con el generador ya terminado, y 1 min después para que Firehose vacíe su buffer. Consola: **Step Functions → State machines → curso-aws-hp-pipeline → Start execution**, con la entrada `{"forzar_fallo": "false"}`, y sigue el grafo en la vista de la ejecución.

Desde la terminal:

```bash
python demo4-pipeline/scripts/ejecutar_pipeline.py
```

**Salida esperada:**

```
  -> Preparar
  -> SilverEnParalelo
  -> JobVentas
  -> JobMaestros
  -> LeerCalidad
  -> CalidadOK
  -> CargarGold
  -> EsperarGold
  -> EstadoGold
  -> GoldTerminado
  -> RefrescarSPICE
  -> NotificarOK
Resultado: SUCCEEDED
```

Llega el email «Pipeline del curso: correcto». Tarda ~2–3 min.

**Qué contar:** `glue:startJobRun.sync` espera a que el job termine sin gastar transiciones. El job de ventas deja `control/calidad/ventas/ultima.json` y `LeerCalidad` lo lee para decidir. La Data API es asíncrona, de ahí el bucle `EsperarGold` → `EstadoGold`.

## 3. Consultar silver en Athena, incluido time travel (≈ 8 min)

```bash
python demo3-catalogo-athena/scripts/athena.py --sql "SELECT count(*) AS filas, count(DISTINCT event_id) AS unicos FROM silver.ventas"
python demo3-catalogo-athena/scripts/athena.py --sql "SELECT cliente_id, segmento, valid_from, valid_to, is_current, es_baja FROM silver.dim_cliente WHERE cliente_id IN ('C-17', 'C-4001', 'C-981') ORDER BY 1, 3"
python demo3-catalogo-athena/scripts/athena.py --sql "SELECT moneda, precio_unitario, importe_bruto, tienda_id FROM silver.ventas WHERE moneda = 'JPY' AND precio_unitario = 6392 AND unidades = 1 LIMIT 3"
```

Time travel: la tabla antes de la ejecución que acabas de lanzar, y sus snapshots:

```sql
SELECT count(*) AS ahora FROM silver.ventas;

SELECT count(*) AS hace_5_min FROM silver.ventas
FOR TIMESTAMP AS OF (current_timestamp - interval '5' minute);

SELECT committed_at, operation, summary['added-records'] AS filas
FROM "silver"."ventas$snapshots" ORDER BY committed_at;
```

**Salida esperada de las versiones de clientes:**

```
  cliente_id  segmento  valid_from  valid_to    is_current  es_baja
  C-17        Standard  1900-01-01  2026-10-28  false       false
  C-17        Premium   2026-10-28  9999-12-31  true        false
  C-4001      Standard  2026-10-28  9999-12-31  true        false
  C-981       Standard  1900-01-01  2026-10-28  false       true
```

**Salida esperada del time travel:** `hace_5_min` tiene menos filas que `ahora`, y la última fila de `$snapshots` es un `append` con las filas nuevas (en las pruebas, 263.178 en la primera carga y ~1.200 en cada ejecución de 2 min). Si la última ejecución es anterior al intervalo, las dos cuentas coinciden: ajusta el intervalo.

**Qué contar:**
- **Time travel:** cada MERGE crea un snapshot, y se puede consultar la tabla tal como estaba. La diapositiva usa `interval '1' hour`.
- **Desduplicación:** `filas = unicos`, frente a los duplicados que había en bronze.
- **EUR:** un JPY de 6.392 son 39,95 €. `descuento` ya es el total de la línea: no se multiplica por unidades.
- **Trampa del SCD2:** en la primera ejecución llegan juntas la carga completa y los cambios. Con «último cambio por clave», C-17 tendría una sola versión Premium desde 1900. Por eso se aplica primero la carga y luego los cambios por `ts_commit`.
- **Granularidad de día.** Las ventas de C-17 del 28-10-2026 anteriores a las 17:23, cuando cambió de segmento, quedan asociadas a la versión Premium. Es una limitación conocida: `valid_from` es una fecha.
- **Data Quality:** `DataFreshness` falla en cuanto el lote contiene histórico, y es lo esperado: no es crítica y solo va al control. Se ve en **AWS Glue → Data quality** o en `ultima.json`.

## 4. Consultar gold en Redshift Query Editor v2 (≈ 6 min)

Consola: **Amazon Redshift → Query editor v2 → hp-retail → dev**.

```sql
SELECT COUNT(*) FROM gold.fct_ventas;
SELECT COUNT(*) FROM gold.fct_ventas WHERE cliente_sk = -1;   -- ventas sin cliente
SELECT * FROM gold.mv_ventas_diarias ORDER BY fecha_sk DESC LIMIT 10;
SELECT pais, SUM(venta_neta) FROM gold.v_dashboard_ventas GROUP BY 1 ORDER BY 2 DESC;
```

**Qué contar:**
- **Clave subrogada:** cada venta enlaza con la versión SCD2 vigente en su fecha, y la de C-17 anterior al 28-10 sigue contando como Standard.
- **Coste:** sin consultas no hay cómputo. Cada activación factura un mínimo de 60 s (4 RPU ≈ 1,50 USD/h). El límite de uso corta a las 10 RPU-hora diarias.
- **Permisos del motor:** `sql/redshift/07_permisos_demo.sql` crea `analista_asia` con RLS sobre `dim_tienda`.

## 5. Ver el dashboard de QuickSight con los datos nuevos (≈ 3 min)

El estado `RefrescarSPICE` del paso 2 ya ha lanzado la actualización del dataset.

1. En Amazon Quick, abre **Datasets → ventas_dashboard**: en el historial de actualizaciones, la última debe estar completada y con más filas.
2. Abre el dashboard `Ventas retail · curso` y recárgalo: la venta de hoy ha cambiado.

El dashboard debe existir antes de este paso: se crea con la [guía de QuickSight](#quicksight-del-dataset-al-dashboard), ~15 min. Se puede montar antes de clase o, si hay tiempo, en directo.

**Salida esperada** (por API, en las pruebas): `COMPLETED`, 266.780 filas y 0 descartadas, las mismas que `gold.fct_ventas`.

## 6. Forzar un fallo en un job y comprobar el Catch y el email (≈ 8 min, con la explicación de reintentos)

```bash
python demo4-pipeline/scripts/ejecutar_pipeline.py --forzar-fallo
```

Entrada en la consola: `{"forzar_fallo": "true"}`.

**Salida esperada:** `JobVentas` y `JobMaestros` tres veces (Retry ×2 con 60 y 120 s de espera), `NotificarFallo`, `Fallido`, `Resultado: FAILED`, email «Pipeline del curso: FALLO» y **gold sin tocar**. Tarda ~6 min: lanzarlo al empezar la explicación.

**Qué contar:** el Catch separa el fallo técnico del de calidad, aunque los dos acaban avisando. Si `pct_cuarentena` supera el 5 %, `CalidadOK` también va a `NotificarFallo`; si supera el 50 %, es el job el que falla, porque la fuente está rota.

Una ejecución sin ficheros nuevos no es un fallo: termina en `SinDatos`, sin email. Compruébalo lanzándola otra vez:

```bash
python demo4-pipeline/scripts/ejecutar_pipeline.py
```

---

## QuickSight: del dataset al dashboard

Terraform crea la fuente de datos `curso-redshift-gold` y el dataset `ventas_dashboard` (SPICE). El resto se hace a mano en clase, en unos 15 minutos.

QuickSight se llama ahora **Amazon Quick** en la consola; la API sigue siendo `quicksight`.

> **Probado por API:** fuente de datos, dataset e importación (265.578 filas, 0 descartadas) y refresco desde la máquina de estados (266.780 filas). **Pendiente de comprobar en la consola:** el análisis y el dashboard, y los nombres de menús de este apartado.

### Antes de la clase (una vez)

1. **Activa la prueba gratuita** de Amazon Quick en `eu-west-1`, con tu email como administrador. **Anota la fecha de fin de la prueba: dura 30 días y después se factura sola, 250 USD/mes por cuenta más 40 USD/mes por usuario.** AWS Budgets solo avisa, no para nada. No actives las preguntas en lenguaje natural. En la cuenta de pruebas, el administrador apareció como `ADMIN_PRO`.
2. **Copia el ARN del usuario** (Administrar cuenta → Usuarios, o `aws quicksight list-users --aws-account-id <ID de cuenta> --namespace default`) en `quicksight_usuario_arn` del `terraform.tfvars` de `demo4-pipeline/infra/`, pon `quicksight_activo = true` y aplica.
3. **Comprueba** que `ventas_dashboard` aparece en Datasets con la importación correcta y el número de filas esperado.

### En clase

1. **Ver el dataset.** Abre `ventas_dashboard`: es SPICE (tamaño e historial de actualizaciones), con el campo calculado de fila `venta_rebajas`. Los agregados no van aquí (diapositiva «Conectar QuickSight con gold»).
2. **Crear el análisis.** «Usar en análisis», con una hoja interactiva.
3. **Campos calculados del análisis:**
   - `ticket_medio = sum(venta_neta) / distinctCount(clave_ticket)`.
   - `pct_rebajas = sum(venta_rebajas) / sum(venta_neta)`, con formato de porcentaje.
4. **Cuatro KPI** en una fila: **Venta neta** (`venta_neta`, suma, EUR), **Unidades** (`unidades`, suma), **Ticket medio** (`ticket_medio`) y **% en rebajas** (`pct_rebajas`).
5. **Líneas «Venta neta semanal por país»:** eje X `fecha` por semana, valor `venta_neta` (suma), color `pais`. Con 120 días de histórico se ven las rebajas de verano.
6. **Barras horizontales «Unidades por color»:** eje Y `color`, valor `unidades` (suma), de mayor a menor. Filtro solo en este visual: `familia = vestidos`.
7. **Filtros y controles** para `fecha` (rango), `pais`, `familia` y `segmento`, cada uno como control en la parte superior y aplicado a todos los visuales.
8. **Publicar** como dashboard `Ventas retail · curso`. Muestra cómo se comparte con un lector y cómo se programa un informe por email, sin hacerlo.
9. **Cerrar el ciclo:** es el paso 5 de la demo.

### Si algo falla

- **El dataset no importa:** prueba la fuente de datos (Validar conexión). Lo más habitual es el security group: el rango de QuickSight en `eu-west-1` (`52.210.255.224/27`) debe estar permitido en el 5439 y el workgroup debe ser público.
- **El dashboard no cambia tras el pipeline:** mira el historial de actualizaciones del dataset y, si falló, el error en `RefrescarSPICE`. Comprueba que el dataset tiene el mismo ID que recibe la máquina.
- **«% en rebajas» sale 0:** el filtro de fecha deja fuera julio y agosto.
- **`SYNTAX_ERROR` en `venta_rebajas`:** QuickSight no admite un booleano como condición. Por eso `es_rebajas` entra como 0 o 1 y la expresión es `ifelse({es_rebajas} = 1, {venta_neta}, 0.0)`.

---

## Si algo falla en el pipeline

- **`SystemExit: 0` en un job:** el script usa `sys.exit`, que Glue marca como FAILED. Debe terminar con `return`.
- **`Status: FAILED` en `GoldTerminado`:** consulta `sys_query_history` en Query editor v2.
- **`CalidadOK` va a `NotificarFallo` sin error:** hay más del 5 % en cuarentena. Consulta `SELECT motivo, count(*) FROM silver.ventas_cuarentena GROUP BY 1`.
- **`ERROR: Materialized view base table "dim_tienda" is not supported`:** una vista materializada no admite tablas con RLS. Por eso usa `gold.tienda_pais`.
- **Redshift no responde tras muchas consultas:** se ha alcanzado el límite de 10 RPU-hora diarias y el workgroup se ha desactivado. Se reactiva al día siguiente.

## Costes

Medido en la cuenta de pruebas el 30-10-2026, con ~265.000 ventas:

| Concepto | Coste |
|---|---|
| **Ejecución completa del pipeline** (dos jobs de ~60 s, ~125 DPU-s cada uno, más el `CALL`) | **~0,05 USD** |
| Primera carga de silver (ventas 259 DPU-s, maestros 186 DPU-s) | ~0,05 USD |
| Fallo forzado (tres intentos de cada job, ~750 DPU-s) | ~0,10 USD |
| Redshift: todas las pruebas de un día | 1.203 RPU-s ≈ 0,13 USD |
| **IP elástica del workgroup público** (aunque no haya consultas) | ~0,005 USD/h ≈ 3,60 USD/mes |
| Secretos de Redshift y `quicksight_ro` | ~0,80 USD/mes |

Glue se calcula a 0,44 USD por DPU-hora y Redshift a ~0,375 USD por RPU-hora. Las cifras de coste son estimaciones a partir de los DPU-s y RPU-s medidos, no de la factura. El tope diario de Redshift (10 RPU-hora) equivale a ~3,75 USD.

**La programación horaria no es gratis:** 24 ejecuciones al día son ~1,20 USD/día si hay datos nuevos, y los jobs se lanzan aunque no los haya. Por eso va desactivada; si la activas, usa `clase_ejecucion_glue = "FLEX"`.

## Limpieza

```bash
cd demo1-ingesta
docker compose down
```

- [x] `docker compose down`.
- [x] Programación horaria **desactivada** (`programacion_activa = false`, por defecto).
- [x] **Redshift se mantiene** para la sesión 3: sin consultas no hay cómputo. La IP elástica sí se cobra (ver Costes).
- [ ] **Cancela Amazon Quick antes de que acaben los 30 días de prueba:** después cuesta ~290 USD/mes. Antes de cancelarla, pon `quicksight_activo = false` y aplica, para que Terraform no apunte a recursos borrados.

Para retirarlo todo al acabar el curso, `terraform destroy` en `demo4-pipeline/infra` y luego en `demo3-catalogo-athena/infra`. Las tablas de silver están en el catálogo y en S3: el `destroy` de la base de datos las quita del catálogo, pero los ficheros siguen en el bucket hasta el `destroy` de `infra/base`.
