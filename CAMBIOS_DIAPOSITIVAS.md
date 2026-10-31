# Cambios propuestos a las diapositivas

Diferencias entre las diapositivas y lo que funciona al probarlo contra AWS. Las citas son del anexo A de `HANDOFF_SESION2.md`.

## Sesión 1

Los cambios de esta sesión ya se aplicaron a las diapositivas y el fichero se borró entonces.

## Sesión 2

### Desviaciones previstas en el handoff

| Diapositiva | Texto actual | Texto propuesto | Motivo |
|---|---|---|---|
| 56 · Silver en paralelo | `"Parameters": { "JobName": "bronze-a-silver-ventas" }` | Añadir `"Arguments": { "--FORZAR_FALLO.$": "$.opciones.forzar_fallo" }` | Permite provocar el fallo del paso 6 desde la entrada de la ejecución |
| 56 · Silver en paralelo | `"Next": "CalidadOK"` | `"Next": "LeerCalidad"` | El resultado de Data Quality está en S3: un estado `LeerCalidad` lo lee con `aws-sdk:s3:getObject` y `States.StringToJson` antes de decidir |
| 26 · SCD2 con MERGE | Siempre cierra la vigente y abre una versión | Si la vigente se abrió ese mismo día, se actualiza | Evita versiones de duración cero |
| Glue Data Quality | Umbral sin concretar | Más del 50 % en cuarentena: el job falla (fuente rota). Más del 5 %: `CalidadOK` va a `NotificarFallo` | Distingue una fuente rota de un lote con errores |

### Encontrado al probar

| Diapositiva | Texto actual | Texto propuesto | Motivo |
|---|---|---|---|
| 24 · Ventas | `.withColumn("pais", F.substring("tienda_id", 1, 2))` | `F.when(F.col("tienda_id").startswith("ONL-"), F.substring("tienda_id", 5, 2)).otherwise(F.substring("tienda_id", 1, 2))` | **Error:** en las tiendas online (`ONL-ES`) devuelve `ON` como país |
| 24 · Ventas | `.join(F.broadcast(cambio), "moneda")` | `.join(F.broadcast(cambio), "moneda", "left")` | **Error:** con INNER JOIN, una moneda desconocida desaparece en silencio y la regla de `moneda` de Data Quality nunca la ve |
| 24 · Ventas | `.filter("unidades >= 1 AND producto_id IS NOT NULL")` | Quitar el filtro | Si se filtra antes, Data Quality no ve esas filas y nunca llegan a cuarentena |
| 29 · Data Quality | `DataFreshness "fecha_venta" <= 24 hours` en las mismas reglas | Evaluarla aparte, sin separar filas | **Error:** a nivel de fila mandaría todo el histórico a cuarentena. Con el histórico, solo el 2,64 % de las filas la cumple. Se añade también `IsComplete "fecha_venta"` |
| 21 · Anatomía de un Glue Job | No muestra cómo terminar | Avisar: para terminar antes de tiempo, usar `return` | `sys.exit(0)` hace que Glue marque el job como `FAILED` con `SystemExit: 0` |
| 26 · SCD2 con MERGE | MERGE + INSERT sobre un lote | Versiones calculadas en orden y un único MERGE por clave + `valid_from` | Es más claro para aplicar la carga completa y los cambios en orden de `ts_commit`, y es idempotente. Se calcula en el driver: son miles de filas |
| 57 · Cargar gold | `"Id.$": "$.Id"`, `"Variable": "$.Status"` | `"ResultPath": "$.gold"`, `"Id.$": "$.gold.Id"`, `"Variable": "$.estado_gold.Status"` | Sin `ResultPath`, cada estado sobrescribe la entrada y se pierde el control de calidad que necesita `NotificarOK` |
| 57 · Cargar gold | `CALL gold.sp_cargar_gold(current_date-1, current_date+1)` | `CALL gold.sp_cargar_gold((current_date-1)::TIMESTAMP, (current_date+1)::TIMESTAMP)` | Los parámetros son `TIMESTAMP`: conversión explícita. La forma sin conversión no se ha probado |
| 57 · Cargar gold | Solo `FINISHED` y `FAILED` | Añadir `ABORTED` a la rama de fallo | Una sentencia cancelada dejaría el bucle en marcha para siempre |
| 56 y siguientes | Empieza en `SilverEnParalelo` | Estado inicial `Preparar` | `forzar_fallo` es opcional: una ejecución sin entrada usa `false` |
| 40 y 47 · Gold | `mv_ventas_diarias` con `JOIN gold.dim_tienda`, y RLS sobre `gold.dim_tienda` | `mv_ventas_diarias` con `JOIN gold.tienda_pais`, tabla auxiliar con `tienda_sk` y `pais` | **Error:** son incompatibles: `Materialized view base table "dim_tienda" is not supported` |
| 47 · Permisos del motor | Termina en `ROW LEVEL SECURITY ON` | Añadir `GRANT IGNORE RLS TO ROLE lector_gold_completo` y `GRANT ROLE lector_gold_completo TO quicksight_ro` | Con RLS activo, quien no tiene política no ve filas: el dashboard quedaría vacío. `IGNORE RLS` no se puede conceder a un usuario, solo a un rol |
| 38 · dim_cliente | Sin `pais` | Con `pais` | El handoff lo incluye como atributo SCD2 |
| Crawlers | El crawler crea `clientes` y `productos` sobre `bronze/cdc/public/` | El crawler rastrea solo `productos`; `bronze.clientes` se crea con DDL (`sql/04_bronze_clientes.sql`) | Con la carga en la raíz, sin `Op`, y los cambios en `AAAA/MM/DD/`, con `Op`, crea tablas `load00000001_parquet` y `2026` y avisa `Found schemas don't match ... Can not create Tables`. Probado con exclusiones y con varios niveles de tabla. Athena sí lee la mezcla en una tabla sin particiones |
| Crawlers | Exclusiones de la diapositiva | Comprobar | No tenía el texto de la diapositiva: usé `**/_SUCCESS`, `**/*.tmp` y `**/_temporary/**` |
| 16 · Athena e Iceberg | `FOR TIMESTAMP AS OF (current_timestamp - interval '1' hour)` y `silver.ventas` | Sin cambios en la diapositiva. El fichero usa `interval '5' second` y `silver.ventas_prueba` | La tabla de prueba es recién creada y falla si se le pide una hora |
| 15 · Explorar bronze | «Top 5 productos por venta neta» | Añadir una nota | Suma importes de monedas distintas, así que dominan los de JPY. Sirve como ejemplo de por qué hace falta silver |
| Conectar QuickSight con gold | `venta_rebajas = ifelse(es_rebajas, venta_neta, 0)` | `ifelse({es_rebajas} = 1, {venta_neta}, 0.0)`, con `es_rebajas` como columna `BIT` en el dataset | **Error:** QuickSight responde `SYNTAX_ERROR`: un booleano no vale como condición. Se comprobó la expresión al crear el dataset; `es_rebajas` queda como `INTEGER` (0 o 1) |
| Suscripción de QuickSight | «QuickSight» | «Amazon Quick (antes QuickSight)» | La consola ya usa el nombre nuevo. La API sigue siendo `quicksight` |
| Suscripción de QuickSight | «No activar usuarios Pro» | Comprobar, y añadir: «al acabar los 30 días se factura sola: 250 USD/mes por cuenta más 40 USD/mes por usuario» | Al activar la cuenta de pruebas, el administrador aparece como `ADMIN_PRO`. Lo que cuesta es importante para alumnos con cuenta de empresa |
| Coste de Redshift | «Sin consultas no hay cómputo» | Añadir: «pero un workgroup público tiene una IP elástica, ~3,60 USD/mes» | El endpoint público lleva una IPv4 que se cobra aunque no haya consultas |

### Comprobado: sin cambios

| Tema | Resultado |
|---|---|
| Athena y `.json.gz` con `Content-Encoding: gzip` | Lee bien: 3.395 líneas en Athena y en S3 el 28-10 |
| Glue, bookmarks y `.json.gz` | Lee y descomprime bien; la segunda ejecución lee 0 filas |
| Redshift Serverless en `eu-west-1` | Admite 4 RPU de base. Sin Enhanced VPC Routing bastan 2 subredes en 2 AZ; se usan 3 |
| Rango de IP de QuickSight en `eu-west-1` | `52.210.255.224/27` |

### Notas (no son cambios)

- **Granularidad de día del SCD2.** Las ventas del 28-10-2026 anteriores al cambio de C-17 (17:23) quedan asociadas a la versión Premium, porque `valid_from` es una fecha. Limitación conocida.
- **Nivel de tabla de los crawlers.** Para `TableLevelConfiguration`, la API cuenta el bucket como nivel 1: `bucket/bronze/cdc/public/productos` es el nivel 5, aunque la documentación diga que la carpeta superior es el 1.
- **Volumen del backfill.** Son ~260.000 eventos, no ~180.000: los factores de fin de semana y rebajas multiplican el volumen, y los 120 días incluyen julio y agosto.
