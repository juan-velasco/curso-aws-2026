# Estado del repositorio al cerrar la sesión 3

Recoge el estado **real** del repositorio y de la cuenta de pruebas el 01-11-2026, comprobado con Terraform, AWS CLI y boto3. Complementa a `ESTADO_SESION1.md` y `ESTADO_SESION2.md`.

Donde aparece `<ID de cuenta>`, el valor real se obtiene con `terraform -chdir=infra/base output -raw account_id`.

---

## 1. Qué falta

| Pieza | Estado |
|---|---|
| Demo 5 | **Completa** y probada contra AWS, con service a 0. **Sin probar:** build en portátil x86 con QEMU, porque el equipo de pruebas es ARM |
| Demo 6: datos, notebook y carga | **Completa** y probada en un space `ml.t3.medium`, de principio a fin. **El modelo no gana a la línea base**: documentado, sin forzar. **Space creado por API y celdas ejecutadas por la API de Jupyter**: sin probar el recorrido por la consola de Studio |
| Demo 6: QuickSight | Dataset creado y refrescado (6.000 filas). **Visual sin hacer**: es a mano, y los nombres de menú del guion están sin comprobar |
| Demo 6: ruta opcional | **Probada:** training job en Spot, registry y batch transform. La aprobación solo se pudo ejercitar con un umbral de mentira (`--wape-base 0.5`), porque con el real el modelo no se aprueba, como debe ser |
| Demo 6: apagado por inactividad | Configurado (60 min). **Sin ver actuar** |
| Demo 6: `terraform destroy` | **Sin probar.** SageMaker crea dos security groups en la VPC que pueden bloquear el borrado |
| Ejercicio F | **Completo.** Terraform, scripts y secuencia de CLI probados contra AWS, y 3 errores típicos provocados (pila temporal `-cli`, ya borrada). `SOLUCION.md` es ahora guion de consola: **la mayoría de formularios revisados en la consola, sin crear nada con ellos, y otros sin abrir (ver la tabla de `SOLUCION.md`)**, así que el recorrido completo por consola sigue sin probar, y el bloque de PowerShell tampoco. **La contraseña de `tienda-vlc-003` del módulo se restableció a un valor que no se guardó: antes de clase, `crear_usuario.py`** |
| Ejercicio G | **Completo** y probado, incluido `destroy`. **Solo 2 hallazgos de ejemplo:** no se ha medido el volumen sin `--tipos` |
| Dashboard de la demo 4 | Lo sigue haciendo el profesor a mano (`ESTADO_SESION2.md`) |

**Pendientes de la sesión 2 (§8 del handoff):**

| Pendiente | Decisión del profesor | Resultado |
|---|---|---|
| RLS de `analista_asia` | Probar | **Funciona, con matices.** Usuario temporal, ya borrado. Con join a `dim_tienda`: CN 45.829 y JP 52.489. **Sin join, `SELECT count(*) FROM gold.fct_ventas` ve las 268.580 filas**, porque la política está en `dim_tienda`. `gold.dim_cliente` no tiene columna `email` |
| Cuarentena | No probar | **Sigue sin probar** en AWS |
| Lake Formation | Dejarlo aplicado | **Sigue aplicado**, 27 elementos en el estado |
| Aviso de Amazon Quick | Hecho | En el guion de la demo 6 |

## 2. Árbol añadido

```
├── ESTADO_SESION3.md
├── HANDOFF_SESION3.md
├── demo5-api-fargate/
│   ├── GUION.md, taskdef.json.tpl
│   ├── infra/                       # main.tf: red, roles, log group
│   └── scripts/                     # generar_taskdef, ip_tarea, comprobar_demo5, limpiar_demo5, tests/
├── demo6-prevision-sagemaker/
│   ├── GUION.md, requirements-opcional.txt
│   ├── infra/                       # main.tf, quicksight.tf
│   ├── sql/                         # unload, fct_prevision, v_prevision_vs_real
│   ├── notebooks/prevision_ventas.ipynb
│   ├── sagemaker/                   # entrenar.py, inferencia.py
│   └── scripts/                     # generar_clima, preparar_datos, cargar_prevision, lanzar_entrenamiento,
│                                    # registrar_publicar, comprobar_demo6, limpiar_demo6, tests/
├── ejercicio-f-cognito/
│   ├── SOLUCION.md, infra/, scripts/ (crear_usuario, probar_api, tests/)
└── ejercicio-g-guardduty-inspector/
    └── SOLUCION.md, infra/, scripts/ (estado_servicios, hallazgos_ejemplo, subir_imagenes, resumen_inspector, tests/)
```

Añadidos después: `HANDOFF_EJERCICIO_F.md`, `ejercicio-f-cognito/cli/` (plantillas de la API para la CLI) y `scripts/tests/test_probar_api.py`.

Cambios en lo existente: `demo4-pipeline/infra` (política `lectura-escritura-ml` y output `quicksight_fuente_arn`), `pyproject.toml`, `requirements-dev.txt` (`pandas`), `.gitignore`, `README.md` y `CAMBIOS_DIAPOSITIVAS.md`.

## 3. Terraform

| Módulo | Estado | Lee de |
|---|---|---|
| `demo5-api-fargate/infra` | Desplegado (13 recursos) | `infra/base`, `demo1-ingesta/infra` |
| `demo6-prevision-sagemaker/infra` | Desplegado (13 recursos, con el dataset de QuickSight) | `infra/base`, `demo4-pipeline/infra` |
| `ejercicio-f-cognito/infra` | Desplegado (12 recursos) | `infra/base` |
| `ejercicio-g-guardduty-inspector/infra` | **Destruido** (estado vacío). Los valores `crear_detector_guardduty = true` y `activar_inspector_ecr = true` siguen en su `terraform.tfvars` local | `infra/base` |
| `demo4-pipeline/infra` | Añadida la política `lectura-escritura-ml` al rol de Redshift | `infra/base` |

Etiquetas: `sesion = 3` y `demo = demo5 | demo6 | ejercicio-f | ejercicio-g`. Proveedores: los de las sesiones anteriores.

**Fuera de Terraform (demo 5):** repositorio ECR `api-ventas` con la imagen `1.0.0`, cluster `hp-retail`, service `api-ventas` a 0 tareas, y la revisión 1 de la task definition. Los borra `limpiar_demo5.py --todo`.

**El security group de la API y el de Redshift admiten una IP concreta**: al cambiar de red, hay que aplicar de nuevo.

## 4. Rutas en S3

| Uso | Ruta |
|---|---|
| Serie y calendario | `ml/ventas_diarias/`, `ml/calendario/` (UNLOAD con `CLEANPATH`) |
| Clima inventado | `ml/clima/clima.parquet` |
| Previsión | `ml/predicciones/fecha_calculo=AAAA-MM-DD/prevision.csv` |
| Ruta opcional | `ml/train/`, `ml/valid/`, `ml/entrada_bt/`, `ml/checkpoints/`, `ml/modelos/`, `ml/codigo/`, `ml/predicciones_bt/` |

## 5. Volumen

| Dato | Valor |
|---|---|
| Generador contra Fargate | 3 min en hora pico: 1.800 eventos, 7 ficheros, 0 perdidos |
| `silver.ventas`, `gold.fct_ventas` | 268.580 filas (eran 266.780) |
| Serie de la previsión | Del 02-07-2026 al 01-11-2026. Atípicos: 30-10 con 11.035 unidades, 31-10 con 0 |
| `gold.fct_prevision` | 1.120 filas, fecha de cálculo 2026-11-01, del 02-11 al 29-11 |
| Dataset SPICE `prevision_vs_real` | 6.000 filas |

## 6. Resultados del modelo

| Modelo | WAPE, validación del 05-10 al 01-11 | Sin los 3 últimos días |
|---|---|---|
| Línea base | **0,349** | **0,197** |
| XGBoost sin clima | 0,374 | |
| XGBoost con clima | 0,381 | 0,227 |
| Training job (XGBoost 1.7-1, con clima) | 0,3766 | |

Con 120 días no se ha visto octubre al entrenar, y la feature con más ganancia es `mes`. Calendario > clima se cumple.

## 7. Qué sigue desplegado y cómo destruirlo

**Nada tiene coste por hora ahora mismo:** 0 tareas en Fargate, 0 apps y 0 spaces en Studio, 0 endpoints, 0 trabajos en curso. GuardDuty e Inspector, desactivados.

**Con coste aunque no se use:**

| Recurso | Coste | Módulo |
|---|---|---|
| **Amazon Quick** | **Prueba hasta el 29-11-2026; después, según la página de precios, ~290 USD/mes.** Pendiente de cancelar | Manual |
| IP elástica del workgroup de Redshift | ~3,60 USD/mes | demo 4 |
| 2 secretos | ~0,80 USD/mes | demo 4 |
| Imagen en ECR (71 MB) | ~0,01 USD/mes | demo 5 |
| EFS del dominio de Studio (12 KB) | Despreciable | demo 6 |
| Objetos en S3 | Céntimos | base |

**Sin coste, desplegado:** red y roles de la demo 5; red, rol, dominio y perfil de la demo 6; user pool y API del ejercicio F; Lake Formation.

**Roles de servicio que crea AWS y se quedan, sin coste:** `AWSServiceRoleForECS`, `AWSServiceRoleForAmazonGuardDuty`, `AWSServiceRoleForAmazonGuardDutyMalwareProtection`, `AWSServiceRoleForAmazonInspector2`, además de los de SageMaker y QuickSight que hubiera.

**Al terminar el curso, en este orden:**

```bash
# 1. Antes de cancelar Amazon Quick: quicksight_activo = false en demo 4 y demo 6, y aplicar. Cancelarla antes del 29-11-2026
python demo6-prevision-sagemaker/scripts/limpiar_demo6.py --todo
terraform -chdir=demo6-prevision-sagemaker/infra destroy          # sin probar: ver §1
python demo5-api-fargate/scripts/limpiar_demo5.py --todo
terraform -chdir=demo5-api-fargate/infra destroy
terraform -chdir=ejercicio-f-cognito/infra destroy
terraform -chdir=demo4-pipeline/infra-lakeformation destroy -parallelism=1
terraform -chdir=demo4-pipeline/infra destroy
terraform -chdir=demo3-catalogo-athena/infra destroy
terraform -chdir=demo1-ingesta/infra destroy
terraform -chdir=infra/base destroy                               # borra el bucket con todo su contenido
```

## 8. Roles IAM nuevos

| Rol | Para qué |
|---|---|
| `curso-aws-hp-ecs-ejecucion` | ECS descarga la imagen y escribe logs. `AmazonECSTaskExecutionRolePolicy` |
| `api-ventas-task` | La API. Solo `api-ventas-firehose-put`, y confianza con `aws:SourceAccount` |
| `curso-aws-hp-sagemaker` | Studio y sus jobs. `AmazonSageMakerFullAccess` y, del bucket del lago, solo `ml/` |

`curso-aws-hp-redshift` añade lectura y escritura sobre `ml/*`.

## 9. Desviaciones respecto a HANDOFF_SESION3.md

Las que afectan a las diapositivas están en `CAMBIOS_DIAPOSITIVAS.md`. Además:

| Tema | Handoff | Real | Motivo |
|---|---|---|---|
| UNLOAD | `ALLOWOVERWRITE` o `CLEANPATH` | `CLEANPATH` | No deja ficheros de otra ejecución |
| `preparar_datos.py` | Lanza `unload.sql` | Además, refresca la vista y crea `fct_prevision` y `v_prevision_vs_real` | Ningún otro script crea ese SQL, y sin refresco falta el último día |
| Orden | No indicado | `preparar_datos.py` antes de `generar_clima.py` | El clima cubre hasta 28 días tras el último día de gold |
| `v_prevision_vs_real` | Vista | `WITH NO SCHEMA BINDING` | `05_vistas.sql` borra y recrea `mv_ventas_diarias`: una vista normal lo impediría. Probado con QuickSight. **No se ha relanzado** `desplegar_redshift.py` con ella |
| Celda `%pip` | Si falta algo | Quitada | La imagen trae `xgboost` 2.1.4, `pandas` 2.3.3, `s3fs` y `matplotlib` |
| Previsión | Con el modelo entrenado | Reentrenada con todo el histórico y `best_iteration + 1` | Si no, ignora los últimos 28 días |
| Métrica del training job | Sin indicar | `metricas.json`, dentro de `model.tar.gz` | El contenedor rechaza `metric_definitions` |
| Registry | «WAPE como métrica» | `CustomerMetadataProperties` y descripción | Sin un informe de calidad en S3 |
| Batch transform | Salida | Crea un modelo temporal desde la versión aprobada y lo borra | Así no quedan modelos sueltos |
| SDK | Fijar la versión si cambia | `sagemaker==2.257.7`, en `requirements-opcional.txt` y entorno aparte | Sus dependencias no deben mezclarse con `requirements-dev.txt` |
| Idle de JupyterLab | 60 min | `idle_timeout` y `min_idle_timeout` a 60, y `max_idle_timeout` a 480 | La API exige mínimo y máximo. Están en `default_space_settings` |
| Space | «Se crea en la demo» | Igual, pero en las pruebas, por API, con imagen `sagemaker-distribution-cpu` | Para poder ejecutar sin navegador |
| Output `bucket_name` en la demo 5 | No pedido | Añadido | Lo usa `comprobar_demo5.py` |
| Output `quicksight_fuente_arn` en la demo 4 | «Léela de su estado» | Añadido | No existía |
| `estado_servicios.py` | Mostrar el estado | También `--guardar` y `--comparar` | Criterio de `destroy`. Compara solo los tipos activos, porque la API añade tipos (`ami`) |
| Plan del user pool (`HANDOFF_EJERCICIO_F.md`) | Valorar Lite | `ESSENTIALS`, explícito en Terraform | Es el plan por defecto, el de la consola de los alumnos y el de las diapositivas. Sin cambios en AWS |
| `comprobar_demo5.py` | | También `--parado` | Criterio de `desired-count 0` |
| Hallazgos de ejemplo | «`[SAMPLE]` por severidad» | Cuenta por `sample: true` | La API no pone `[SAMPLE]` en el título |
| Pruebas | Lanzar el notebook en Studio | Antes, en local, sin escribir en S3 | Para detectar errores sin pagar el space |

## 10. Versiones y tests

| Componente | Versión |
|---|---|
| SageMaker Distribution (imagen CPU por defecto de la API) | Python 3.12.15, xgboost 2.1.4, pandas 2.3.3, numpy 1.26.4, s3fs 2026.9.0, pyarrow 21.0.0, sin SDK `sagemaker` |
| Contenedor de entrenamiento | `sagemaker-xgboost:1.7-1` |
| SDK `sagemaker` | 2.257.7 |
| `pandas` en desarrollo | 3.1.0. Los tests del notebook usan esta; en Studio corre 2.3.3 |

```bash
pip install -r requirements-dev.txt
pytest                          # 128 tests, ~20 s, sin AWS
ruff check .
terraform fmt -check -recursive
```

Contra AWS:

```bash
python demo5-api-fargate/scripts/comprobar_demo5.py --parado
python demo6-prevision-sagemaker/scripts/comprobar_demo6.py
python ejercicio-f-cognito/scripts/probar_api.py
python ejercicio-g-guardduty-inspector/scripts/estado_servicios.py --comparar
```
