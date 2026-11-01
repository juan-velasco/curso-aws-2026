# Guion · Demo 6: previsión de ventas con SageMaker

**Flujo:** `gold` → UNLOAD a S3 → notebook en SageMaker Studio (features, split temporal, XGBoost) → previsión de 28 días en S3 → COPY a `gold.fct_prevision` → QuickSight.
**Duración:** ~45 min.
**Coste:** por debajo de 1 USD. Estimaciones, sin factura: space `ml.t3.medium` ~0,05 USD/h (2 h, ~0,10 USD), UNLOAD y COPY, unos céntimos de Redshift. Ruta opcional: 58 s facturados de `ml.m5.large` en Spot y un batch transform de minutos, unos céntimos.

**Nunca se crea un endpoint.** Todos los comandos se lanzan desde la **raíz del repositorio**. Requisito: demo 4 con gold cargado.

> **Probado** el 01-11-2026 contra AWS, en un space `ml.t3.medium`, **creado por API y ejecutando las celdas por la API de Jupyter**. **Sin probar:** crear el space y subir el notebook desde la consola, el apagado a los 60 min y el visual de QuickSight.

> **Amazon Quick** se factura sola al terminar la prueba, el 29-11-2026. **Antes de esa fecha**, pon `quicksight_activo = false` en demo 4 y demo 6, aplica ambos y cancela. Si la clase es posterior, enseña el paso 6 con capturas.

---

## Antes de clase

```bash
cd demo6-prevision-sagemaker/infra
terraform init && terraform apply     # 12 recursos: red, rol, dominio y perfil. Unos 5 min
cd ../..
python demo6-prevision-sagemaker/scripts/preparar_datos.py
python demo6-prevision-sagemaker/scripts/generar_clima.py
```

Lanza `generar_clima.py` **después** de `preparar_datos.py`: cubre hasta 28 días tras el último día de gold, y `preparar_datos.py` es quien refresca la vista.

**Salida esperada:**

```
fct_prevision.sql
v_prevision_vs_real.sql
unload.sql
  ml/ventas_diarias/: 4 ficheros, 22 KB
  ml/calendario/: 1 ficheros, 20 KB
Clima inventado: 755 filas, de 2026-07-02 a 2026-11-29, en s3://.../ml/clima/clima.parquet
```

Con Amazon Quick activa, añade `quicksight_activo = true` y `quicksight_usuario_arn` a `terraform.tfvars` y repite `terraform apply`. El dataset exige que la vista ya exista.

**Prepara el visual antes de clase** ([paso 6](#6-visual-de-real-frente-a-previsto-y-parar-el-space-≈-10-min)).

---

## 1. Abrir Studio y arrancar un space de JupyterLab (≈ 5 min)

Consola: **SageMaker AI → Domains → curso-aws-hp → User profiles → profesor → Open Studio**. En **JupyterLab → Create JupyterLab space**, crea un space privado, con `ml.t3.medium`, y **Run space**. Abre el JupyterLab y sube `notebooks/prevision_ventas.ipynb`.

**Qué contar:** el dominio no cuesta nada por sí mismo. Cuesta el space **mientras está en marcha**, y su disco EBS mientras exista. El dominio apaga JupyterLab tras 60 min sin actividad, como red de seguridad.

## 2. UNLOAD desde gold y carga de calendario y clima (≈ 5 min)

Enseña `sql/unload.sql` (ya lanzado con `preparar_datos.py`), y ejecuta las secciones **Parámetros** y **1. Carga** del notebook.

**Salida esperada:** `ventas (4880, 4), calendario (1461, 12), clima (755, 4)`.

**Qué contar:** el clima **es inventado**, y el histórico no tiene efecto del clima. `CLEANPATH` permite repetir el UNLOAD sin que queden ficheros antiguos.

## 3. Features, split temporal y línea base (≈ 10 min)

Secciones 2 a 5.

**Salida esperada:** `Corte: 2026-10-04. Entrenamiento 3800 filas, validación 1120 filas.` y `WAPE línea base: 0.349`.

**Qué contar:**
- **Serie completa:** un día sin ventas también es un dato.
- **Sin fuga:** `lag_28` y `media_28` van desplazadas 28 días, porque es lo que se conocerá al prever. `lag_364` está vacía con 120 días, y XGBoost acepta NaN.
- **Split temporal:** nunca aleatorio en una serie temporal.

## 4. Entrenar XGBoost y comparar el WAPE con y sin clima (≈ 10 min)

Secciones 6 y 7. Tarda menos de 1 s.

**Resultado real (01-11-2026):**

| Modelo | WAPE |
|---|---|
| Línea base | **0,349** |
| XGBoost sin clima | 0,374 |
| XGBoost con clima | 0,381 |

**El modelo NO gana a la línea base con estos datos, y no se ha forzado.** Es el mejor mensaje de la demo: *sin línea base, no te habrías enterado*. Por qué:
- **Solo hay 120 días, y 3 meses de entrenamiento.** La feature con más ganancia es `mes`, y octubre (la validación) no se ha visto al entrenar.
- **Días atípicos en la validación:** 11.035 unidades el 30-10 (los generadores de prueba) y 0 el 31-10. Sin esos últimos 3 días, el WAPE baja a 0,197 (base) y 0,227 (modelo): sigue ganando la base.

**Importancia (ganancia):** `mes` 60,4 · `familia` 41,1 · `lag_28` 8,0 · `media_28` 3,5 · `pais` 3,5 · `dia_semana` 3,5 · `semana_iso` 1,1 · `temp_media` 0,7 · `lluvia_mm` 0,6. **Calendario > clima**, como se espera de un clima aleatorio, que además empeora el WAPE. Los valores cambian al añadir datos.

## 5. Previsión de 28 días a S3 y COPY a `gold.fct_prevision` (≈ 5 min)

Sección 8. **Salida esperada:** `1120 filas en s3://.../ml/predicciones/fecha_calculo=2026-11-01/prevision.csv`. Después, en la terminal:

```bash
python demo6-prevision-sagemaker/scripts/cargar_prevision.py
```

**Salida esperada:** `gold.fct_prevision: 1120 filas con fecha de cálculo 2026-11-01.` (5 países × 8 familias × 28 días) y, con Quick activa, `Dataset prevision_vs_real refrescado: 6000 filas.` Se puede repetir: borra esa fecha de cálculo antes del COPY.

**Qué contar:** la tabla guarda **cada fecha de cálculo**, y la vista muestra la más reciente. Cuando lleguen las ventas reales, se podrá medir el WAPE según la antelación.

## 6. Visual de real frente a previsto y parar el space (≈ 10 min)

**Nombres de menú sin comprobar en la consola de Amazon Quick.**

1. **Datasets → `prevision_vs_real`** (SPICE): comprueba la fecha de la última actualización.
2. Abre el análisis de la demo 4, o crea uno, y añade el dataset.
3. **Gráfico de líneas:** eje X `fecha` (día); valores `unidades_reales` (suma) y `unidades_previstas` (suma). Las reales terminan el último día con datos, y las previstas siguen 28 días más.
4. **Controles** para `pais` y `familia`. Muestra una familia sensible a la temporada (`abrigos` o `baño`) en un país.
5. **Mensaje:** lo previsto es la línea de la última fecha de cálculo. Con las ventas reales, la vista permitirá medir el WAPE según la antelación.
6. Si Amazon Quick ya no está activa, muestra una captura preparada antes.

**Para el space:** en Studio, **Stop space**, o:

```bash
python demo6-prevision-sagemaker/scripts/limpiar_demo6.py
python demo6-prevision-sagemaker/scripts/comprobar_demo6.py
```

**Salida esperada de la comprobación:**

```
Criterios de aceptación
  [OK] Ficheros en ml/ventas_diarias/  (4)
  [OK] Ficheros en ml/calendario/  (1)
  [OK] Ficheros en ml/clima/  (1)
  [OK] Ficheros en ml/predicciones/  (1)
  [OK] gold.fct_prevision con 28 días por serie  (40 series, 1120 filas)
  [OK] gold.v_prevision_vs_real devuelve filas  (6000)
  [OK] Ningún endpoint
  [OK] Ninguna app de Studio en InService
  [OK] Ningún training job en curso
  [OK] Ningún batch transform en curso
```

---

## Ruta opcional: training job, registry y batch transform (≈ 15 min)

Para las diapositivas 56 y 57. Necesita un **entorno aparte**: la imagen de Studio no trae el SDK, y la versión 3 retiró los estimadores.

1. En el notebook, pon `GENERAR_RUTA_OPCIONAL = True` y ejecuta la sección 9. Escribe `ml/train/`, `ml/valid/` y `ml/entrada_bt/`.
2. Lanza el entrenamiento:

   ```bash
   python -m venv .venv-sagemaker && source .venv-sagemaker/bin/activate
   pip install -r demo6-prevision-sagemaker/requirements-opcional.txt
   python demo6-prevision-sagemaker/scripts/lanzar_entrenamiento.py
   deactivate && source .venv/bin/activate
   ```
   ```powershell
   py -3.12 -m venv .venv-sagemaker; .venv-sagemaker\Scripts\Activate.ps1
   pip install -r demo6-prevision-sagemaker/requirements-opcional.txt
   python demo6-prevision-sagemaker/scripts/lanzar_entrenamiento.py
   deactivate; .venv\Scripts\Activate.ps1
   ```

   **Salida real:** `wape=0.3766`, `Training seconds: 144`, `Billable seconds: 58`, `Managed Spot Training savings: 59.7%`.

3. Registra con el WAPE de la línea base del notebook:

   ```bash
   python demo6-prevision-sagemaker/scripts/registrar_publicar.py --wape-base 0.349
   ```

   **Salida real:** `No se aprueba ni se publica: WAPE 0.3766 no mejora a la línea base 0.3490.` La versión queda en `PendingManualApproval`. **Es el comportamiento correcto.**

4. **Para enseñar la publicación**, di en voz alta que el umbral es de mentira y lanza `--wape-base 0.5`. Aprueba la versión, crea un modelo temporal desde ella, lanza el batch transform en `ml.m5.large` y borra el modelo temporal. **Salida real:** 1.120 líneas en `ml/predicciones_bt/futuro.csv.out`. Son las mismas 1.120 filas de `entrada_bt`, en el mismo orden.

## Si algo falla

- **`Access Denied` en el UNLOAD o el COPY:** falta aplicar `demo4-pipeline/infra`, que da al rol de Redshift acceso a `ml/*`.
- **`temp_media` vacía en los días futuros:** lanza `generar_clima.py` después de `preparar_datos.py`.
- **`preparar_datos.py` termina y el último día no aparece:** la máquina de estados solo carga ayer y hoy. Revisa `gold.fct_ventas`.
- **`SageMaker Image ARN is required` al crear la app por API:** indica `SageMakerImageArn`. La imagen en `eu-west-1` es `arn:aws:sagemaker:eu-west-1:470317259841:image/sagemaker-distribution-cpu`.
- **`You can't override the metric definitions`:** el contenedor de XGBoost no admite `metric_definitions` propias. Por eso el WAPE viaja en `metricas.json`, dentro de `model.tar.gz`.
- **`module 'xgboost.callback' has no attribute 'TrainingCheckpoint'`:** en la versión 1.7 se escribe `TrainingCheckPoint`.

## Limpieza

```bash
python demo6-prevision-sagemaker/scripts/limpiar_demo6.py          # para las apps
python demo6-prevision-sagemaker/scripts/limpiar_demo6.py --todo   # también spaces (su EBS tiene coste) y modelos registrados
cd demo6-prevision-sagemaker/infra && terraform destroy && cd ../..
```

Un space parado sigue pagando su EBS, ~0,50 USD/mes por 5 GB (estimación): al terminar el curso, usa `--todo`.

**`terraform destroy` del dominio sin probar.** SageMaker crea dos security groups en la VPC, y pueden bloquear el borrado de la VPC. Si pasa, bórralos a mano y repite.
