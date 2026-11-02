# Estado actual

Situación del repositorio y de la cuenta de pruebas el **02-11-2026**. Las piezas se probaron contra AWS entre el 30-10 y el 01-11; el 02-11 se revisaron los guiones sin cambiar nada en AWS.

Detalle técnico en [REFERENCIA.md](REFERENCIA.md). Diferencias con las diapositivas en [CAMBIOS_DIAPOSITIVAS.md](CAMBIOS_DIAPOSITIVAS.md).

## Pendiente del profesor

| Qué | Cuándo |
|---|---|
| **Cancelar Amazon Quick.** Antes, `quicksight_activo = false` en demo 4 y demo 6, y aplicar. Si no, según la página de precios, ~290 USD/mes | **Antes del 29-11-2026** |
| Fijar la contraseña de `tienda-vlc-003` con `python ejercicio-f-cognito/scripts/crear_usuario.py`: se restableció a un valor que no se guardó | Antes de la clase de Cognito |
| Crear el análisis y el dashboard de la demo 4, y el visual de la demo 6: son a mano, y sus nombres de menú están sin comprobar | Antes de clase |
| Aplicar `demo5-api-fargate/infra`: tu IP ha cambiado desde el último `apply`, y el security group no te deja entrar a `/health` | Antes de la demo 5 |
| Aplicar `demo4-pipeline/infra`, solo si conectas a Redshift directamente desde tu equipo. La misma IP; la Data API, Athena y Query Editor v2 no la necesitan | Si hace falta |
| Recorrer el ejercicio F en la consola: ver [sin demostrar](#sin-demostrar) | Antes de clase |

## Piezas

| Pieza | Estado | Falta |
|---|---|---|
| Base y demo 1 | Probadas | SSO dentro de Docker |
| Demo 2 | Probada y destruida, con sus ficheros en `bronze/cdc/` | |
| Demo 3 | Probada | |
| Demo 4: silver, gold y orquestación | Probada, con ejecución correcta, sin datos y con fallo forzado | Cuarentena con datos reales: siempre vacía, porque la API ya valida. La rama `pct_cuarentena > 5` y el umbral del 50 %, solo en tests locales |
| Demo 4: QuickSight | Fuente, dataset y refresco, probados por API | Análisis y dashboard |
| Lake Formation | Aplicado; criterios probados por API, y ciclo `destroy` + `apply` | Vista de la consola. Puede quedar un opt-in residual: ver el guion |
| RLS de `analista_asia` | Funciona al unir con `dim_tienda`: solo JP y CN | **Sin unir, `SELECT count(*) FROM gold.fct_ventas` ve todas las filas**, porque la política está en `dim_tienda`. `gold.dim_cliente` no tiene `email` |
| Demo 5 | Probada, con el service a 0 | Build en x86 con QEMU |
| Demo 6: datos, notebook y carga | Probados en un space `ml.t3.medium`, creado por API. **El modelo no gana a la línea base:** documentado, sin forzar | Crear el space y subir el notebook desde la consola. Visual. Apagado a los 60 min. `terraform destroy` del dominio |
| Demo 6: ruta opcional | Training job en Spot, registry y batch transform, probados. La aprobación solo con un umbral de mentira (`--wape-base 0.5`) | |
| Ejercicio F | Terraform, scripts, CLI y 3 errores típicos, probados. Desplegado | Recorrido por consola y PowerShell |
| Ejercicio G | Probado, incluido `destroy`. Destruido | Volumen de hallazgos sin `--tipos`: solo se generaron 2 |

## Qué hay desplegado

**Nada tiene coste por hora ahora mismo:** 0 tareas en Fargate, 0 spaces en Studio, 0 endpoints. GuardDuty e Inspector, desactivados.

| Con coste aunque no se use | Coste | Módulo |
|---|---|---|
| **Amazon Quick** | **Prueba hasta el 29-11-2026; después, ~290 USD/mes.** La API no muestra que la cuenta esté en prueba | Manual |
| IP elástica del workgroup de Redshift | ~3,60 USD/mes | demo 4 |
| 2 secretos | ~0,80 USD/mes | demo 4 |
| Imagen en ECR (71 MB) | ~0,01 USD/mes | demo 5 |
| EFS del dominio de Studio | Despreciable | demo 6 |
| Objetos en S3 | Céntimos | base |

**Sin coste, desplegado:** Firehose y alarma (demo 1); catálogo, crawler y workgroup (demo 3); red, jobs de Glue, máquina de estados y Scheduler **desactivado** (demo 4); Lake Formation; red y roles (demo 5); red, rol, dominio y perfil (demo 6); user pool y API (ejercicio F).

**Fuera de Terraform (demo 5):** repositorio ECR `api-ventas` con la imagen `1.0.0`, cluster `hp-retail`, service `api-ventas` a 0 tareas y la revisión 1 de la task definition. Los borra `limpiar_demo5.py --todo`.

**Roles que crea AWS y se quedan, sin coste:** `AWSServiceRoleForECS`, `AWSServiceRoleForAmazonGuardDuty`, `AWSServiceRoleForAmazonGuardDutyMalwareProtection`, `AWSServiceRoleForAmazonInspector2`, y los de SageMaker y QuickSight.

## Al terminar el curso

En este orden, con la terminal [preparada](../README.md#preparar-la-terminal):

```bash
# 1. Antes de cancelar Amazon Quick: quicksight_activo = false en demo 4 y demo 6, y aplicar
python demo6-prevision-sagemaker/scripts/limpiar_demo6.py --todo
terraform -chdir=demo6-prevision-sagemaker/infra destroy          # sin probar: SageMaker crea 2 security groups que pueden bloquear el borrado de la VPC
python demo5-api-fargate/scripts/limpiar_demo5.py --todo
terraform -chdir=demo5-api-fargate/infra destroy
terraform -chdir=ejercicio-f-cognito/infra destroy
terraform -chdir=demo4-pipeline/infra-lakeformation destroy -parallelism=1
terraform -chdir=demo4-pipeline/infra destroy
terraform -chdir=demo3-catalogo-athena/infra destroy
terraform -chdir=demo1-ingesta/infra destroy
terraform -chdir=infra/base destroy                               # borra el bucket con todo su contenido
```

## Validación de los guiones

Revisión del 02-11-2026, sin cambios en AWS: **no demuestra que funcionen de principio a fin.** Las consultas de Athena sí guardan resultados en `athena-results/`, que caducan a los 7 días.

### Qué se ha comprobado

| Comprobación | Resultado |
|---|---|
| Comandos de todos los guiones, `SOLUCION.md` y README, frente a la ayuda de AWS CLI y el código | 62 llamadas a scripts, 80 comandos `aws`, 187 flags, 15 outputs y 39 enlaces: sin fallos tras corregir |
| `terraform validate` y `terraform plan` en los 10 módulos | Sin cambios, salvo los esperados: demo 2 (31 por crear), ejercicio G (8) y la IP en los security groups de demo 4 y demo 5 |
| `pytest`, `ruff`, `terraform fmt` | 130 tests en verde |
| Entorno limpio solo con `requirements.txt` | Los scripts arrancan. `lanzar_entrenamiento.py` necesita además `requirements-opcional.txt`, como dice el guion |
| Docker en local | Las dos imágenes se construyen, y también la de la API para ARM64, sin subirla. La API queda `healthy`, y `curl` y `evento_invalido.py` dan el 422 esperado. **El generador no se lanzó** |
| Comprobadores contra AWS | Demo 1 (con los datos del 01-11), demo 3, demo 4, demo 5 `--parado`, demo 6 y `estado_servicios.py`: en verde |
| Consultas de las demos 3 y 4 en Athena y Redshift | Devuelven lo que dicen los guiones, incluidas las versiones SCD2 de C-17, C-4001 y C-981. Faltan las de los pasos que crean tablas |
| Nombres de los guiones frente a lo desplegado | Coinciden: alarma, crawler, service, repositorio, log group, máquina de estados, dominio, perfil, rol, user pool y datasets |

### Qué se ha corregido

| Problema | Consecuencia | Arreglo |
|---|---|---|
| Los guiones llevaban `--profile curso`, y scripts y Docker usan `curso` si falta `AWS_PROFILE` | Con otro perfil fallaban con `ProfileNotFound` | [Preparar la terminal](../README.md#preparar-la-terminal): `AWS_PROFILE`, `AWS_REGION` y `TF_VAR_perfil` |
| La demo 5 no indicaba región | **Con un perfil en otra región, como `eu-west-3`, crearía el repositorio y el cluster allí** | `AWS_REGION` y aviso en el guion |
| La demo 1 pedía el email solo en la base | Sin el del módulo no hay suscripción ni correo, y son 7 recursos, no los 9 anunciados | Paso añadido, con las dos cifras |
| La demo 2 anunciaba 30 recursos | Son 31 | Corregido |
| La demo 3 no exigía la demo 2 | Sin ella, el crawler no crea `bronze.productos` y `bronze.clientes` sale vacía | Requisito añadido |
| Demos 2 y 5 sin aviso al repetirlas | La 2 altera las cifras de las demos 3 y 4, y en la 5 fallan `create-repository` y `create-service` | Avisos añadidos |
| `comprobar_bronze.py --fecha` comparaba con el generador de otro día | `KO` falso | Solo compara el día de la ejecución, con test |
| Ejercicio F sin PowerShell en la Fase 2 | Los comandos de bash no sirven en Windows | Bloque añadido, sin probar |
| Enlace roto en la demo 6 y comando ambiguo en el README | | Corregidos |

### Sin demostrar

Hay que ejecutarlo para saberlo. Sobre la cuenta actual no se puede repetir sin destruir antes o alterar los datos:

- **El recorrido completo desde una cuenta vacía**, siguiendo los guiones en orden, con las correcciones de arriba. Cada pieza funcionó al construirse, pero no se ha lanzado seguida.
- **Comandos que crean o cambian recursos:** todos los `terraform apply` y `destroy`, DMS, Docker enviando a Firehose, Fargate, `crear_silver`, `desplegar_redshift`, el pipeline, el notebook y la ruta opcional. Se probaron al construirlos; desde entonces han cambiado guiones y `comprobar_bronze.py`.
- **`AWS_REGION` y `TF_VAR_perfil` en un recorrido real:** se ha usado `AWS_PROFILE=default`, con `perfil` ya en los `terraform.tfvars`.
- **Todos los bloques de PowerShell:** revisados por lectura.
- **Pasos de consola:** ejercicio F (ver su tabla), dashboard y visual de QuickSight, Studio, Lake Formation.
- **`probar_api.py`:** la contraseña no está guardada.
- **Build en x86 y SSO dentro de Docker.**
