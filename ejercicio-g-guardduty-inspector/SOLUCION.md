# Solución · Ejercicio G: GuardDuty e Inspector

**Probado contra AWS** el 01-11-2026, incluido `destroy`: el estado final coincide con el inicial. **Se generaron solo 2 hallazgos de ejemplo**, de un tipo concreto, para no llenar el buzón: **no se ha medido** cuántos salen sin `--tipos` ni cuántos correos llegan.

**En cada terminal nueva:** define el perfil y la región ([cómo](../README.md#preparar-la-terminal)).

## Antes de crear nada

En una cuenta de empresa, GuardDuty e Inspector suelen estar **activados y gestionados por la organización**.

```bash
python ejercicio-g-guardduty-inspector/scripts/estado_servicios.py --guardar
```

**Salida en la cuenta de pruebas:**

```
GuardDuty (eu-west-1): sin detector
  Administrador: ninguno (esta cuenta)
Inspector (eu-west-1): {'codeRepository': 'DISABLED', 'ec2': 'DISABLED', 'ecr': 'DISABLED', 'lambda': 'DISABLED', 'lambdaCode': 'DISABLED'}
  Administrador delegado: ninguno
Para terraform.tfvars:
  crear_detector_guardduty = true
  activar_inspector_ecr = true
```

**Copia esos dos valores a `terraform.tfvars`.** Con el servicio ya activo o gestionado, salen en `false`: Terraform no lo toca, y `destroy` **nunca desactiva lo que no activó**. Si los gestiona la organización, el ejercicio se limita a explorar los hallazgos en la consola; la regla de EventBridge y el tema SNS siguen siendo tuyos.

**Coste:** prueba gratuita de 30 días en GuardDuty y de 15 en Inspector. Fuera de la prueba, se paga por uso. Por eso se destruye al acabar.

## Con Terraform y los scripts

```bash
cd ejercicio-g-guardduty-inspector/infra
terraform init && terraform apply      # 8 recursos. Confirma el correo de SNS
cd ../..
python ejercicio-g-guardduty-inspector/scripts/hallazgos_ejemplo.py --tipos "Backdoor:EC2/C&CActivity.B"
python ejercicio-g-guardduty-inspector/scripts/subir_imagenes.py
python ejercicio-g-guardduty-inspector/scripts/resumen_inspector.py
```

**Requisito:** la imagen de `api-ventas` de la demo 5, subida hace menos de 30 días.

Sin `--tipos`, GuardDuty genera uno de cada tipo y llega **un correo por cada hallazgo grave**. Hazlo una vez, en clase, sabiendo que llena el buzón.

**Lleva las imágenes subidas y escaneadas antes de clase.** En la prueba, los dos escaneos terminaron en menos de 25 min: `api-ventas` antes y `python:3.8`, de 364 MB, después.

## Respuestas esperadas

Las cifras son de la prueba, y cambian: Inspector reevalúa las imágenes a medida que se publican CVE.

**¿Cuántos hallazgos críticos tiene cada imagen?**

| Imagen | Total | Críticos | Altos | Medios | Bajos | Informativos | Sin clasificar |
|---|---|---|---|---|---|---|---|
| `curso-imagen-antigua:3.8` (`python:3.8`) | 8.401 | **431** | 2.976 | 2.821 | 85 | 198 | 1.890 |
| `api-ventas:1.0.0` (`python:3.12-slim`) | 24 | **0** | 5 | 14 | 3 | 0 | 2 |

**¿Qué paquete concentra más CVE?**

| `python:3.8` | CVE | `api-ventas` | CVE |
|---|---|---|---|
| **`linux`** (cabeceras del kernel) | 7.679 | **`glibc`** | 15 |
| `imagemagick` | 196 | `pip` | 6 |
| `postgresql-15` | 47 | `sqlite3` | 2 |
| `python3.11` | 41 | `zlib` | 1 |
| `openssl` | 40 | | |

**¿Llegó el email?** Sí, uno por cada uno de los 2 hallazgos de severidad 8,0, como JSON del evento. **Búscalo en el correo no deseado:** en la prueba no se vio a la primera. `NumberOfNotificationsDelivered` del tema SNS, en CloudWatch, confirma la entrega.

## Qué contar

- **Imagen slim:** menos paquetes, menos superficie. Mismo lenguaje, 350 veces menos hallazgos, y ningún crítico. Muchos de los de `python:3.8` no afectan en la práctica: `linux` son cabeceras, no un kernel en marcha.
- **Escaneo básico y mejorado:** al activar Inspector para ECR, el registro pasa de `BASIC` a `ENHANCED`. El básico de `scanOnPush` había visto 18 hallazgos en la imagen de la API, y Inspector, 24.
- **Hallazgos de ejemplo:** en la API, `Title` no lleva `[SAMPLE]`. La marca es `"sample": true`, dentro de `Service.AdditionalInfo.Value`. El script la usa para contarlos.
- **Regla:** patrón de la diapositiva 72, severidad ≥ 7. Es el primer paso de una respuesta automática.

## Limpieza

```bash
cd ejercicio-g-guardduty-inspector/infra && terraform destroy && cd ../..
python ejercicio-g-guardduty-inspector/scripts/estado_servicios.py --comparar
```

`destroy` desactiva solo lo que se activó y borra el repositorio `curso-imagen-antigua` con sus imágenes. **Salida esperada:** `El estado coincide con el inicial.` El registro de ECR vuelve a `BASIC`.

**Quedan en la cuenta, sin coste:** los roles `AWSServiceRoleForAmazonGuardDuty`, `AWSServiceRoleForAmazonGuardDutyMalwareProtection` y `AWSServiceRoleForAmazonInspector2`, que crea AWS. **La imagen de `api-ventas` se queda:** la borra `limpiar_demo5.py --todo`.

Si `--comparar` muestra un cambio, revisa que `crear_detector_guardduty` y `activar_inspector_ecr` estuvieran bien.
