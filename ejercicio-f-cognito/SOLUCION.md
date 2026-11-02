# Solución · Ejercicio F: proteger una API con Cognito

Los alumnos lo montan **a mano**. Este repositorio es la solución de referencia y el plan B: guion de consola, comandos de CLI equivalentes y un módulo de Terraform.

**Terminado cuando** la misma URL da **401 sin token y 200 con token**.

**En cada terminal nueva:** define el perfil y la región ([cómo](../README.md#preparar-la-terminal)). También hace falta para el `admin-set-user-password` del paso 3 de la consola.

**Coste:** sin coste por hora; una API sin tráfico y un user pool con un usuario quedan en el nivel gratuito.

| Qué | Estado (01-11-2026) |
|---|---|
| Terraform y scripts | **Probados** contra AWS |
| [Comandos de CLI](#fase-1-con-la-cli) | **Probados** contra AWS, con sufijo `-cli`, y borrados después. **El bloque de PowerShell no**: no había PowerShell en el equipo de pruebas |
| [Errores típicos](#errores-típicos) | **Provocados** contra AWS |
| [Pasos de consola](#fase-1-en-la-consola) | **Revisados en la consola, sin crear nada con ellos:** asistente del user pool, edición del app client, *Create user*, *Create method*, *Create authorizer* y *Method request*. **Sin abrir, escritos a partir de la API y de la documentación:** *Create group*, el formulario de nombre de la API REST, *Integration response → Edit*, *Deploy API* y la edición de *Authorization*. Lo dudoso se marca como *sin comprobar* |

---

## Fase 1 en la consola

Región **Europa (Irlanda)**.

### 1. User pool `tiendas`

1. **Amazon Cognito → User pools → Create user pool.** Se abre *Set up resources for your application*, que crea a la vez el user pool y el app client.
2. **Application type:** *Single-page application (SPA)*. **No dejes *Traditional web application***, la opción marcada por defecto: es de servidor. *Sin comprobar:* que SPA cree el cliente sin secret. Se ve en el paso 2.
3. **Name your application:** `curso-hola`.
4. **Options for sign-in identifiers:** marca solo *Username*.
5. **Self-registration:** **desmarca** *Enable self-registration*. Viene marcada, y con ella cualquiera puede darse de alta.
6. **Required attributes for sign-up:** el asistente avisa de que «con username solo, hay que exigir email o teléfono». *Sin comprobar:* si lo exige con el autorregistro desactivado. Si lo pide, elige *email* y rellénalo al crear el usuario.
7. **Create user directory**. Es la única confirmación. **Identificadores y atributos no se pueden cambiar después.**
8. **Overview → Rename:** ponle `tiendas`. El asistente no pregunta el nombre.

El plan no se elige aquí: según la documentación, es *Essentials* por defecto. Se ve en **Settings → Feature plan**.

```bash
POOL=$(aws cognito-idp create-user-pool --pool-name tiendas$S --query UserPool.Id --output text)
```

### 2. App client sin secret, con `ALLOW_USER_PASSWORD_AUTH`

1. **Applications → App clients →** `curso-hola`. **Client secret** debe mostrar `-`. Copia el **Client ID**.
2. **Edit → Authentication flows:** marca *Sign in with username and password: ALLOW_USER_PASSWORD_AUTH*. *Get new user tokens from existing authenticated sessions: ALLOW_REFRESH_TOKEN_AUTH* debe seguir marcada. **Save changes.**

```bash
CLIENT_ID=$(aws cognito-idp create-user-pool-client --user-pool-id $POOL --client-name curso-hola$S --no-generate-secret \
  --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH --query UserPoolClient.ClientId --output text)
```

### 3. Usuario de prueba con contraseña permanente, en el grupo `tiendas`

1. **User management → Groups → Create group:** `tiendas`.
2. **User management → Users → Create user:** *Don't send an invitation*, **User name** `tienda-vlc-003`, *Set a password*.
3. **La consola solo admite una contraseña temporal** (*Temporary password*), así que el usuario queda en `FORCE_CHANGE_PASSWORD`. **Hazla permanente con la CLI:** es el comando `admin-set-user-password` de abajo.
4. Abre el grupo `tiendas` y añade el usuario. El estado debe ser `Confirmed`.

```bash
aws cognito-idp create-group --user-pool-id $POOL --group-name tiendas
aws cognito-idp admin-create-user --user-pool-id $POOL --username tienda-vlc-003 --message-action SUPPRESS
aws cognito-idp admin-set-user-password --user-pool-id $POOL --username tienda-vlc-003 --password "$PASSWORD" --permanent
aws cognito-idp admin-add-user-to-group --user-pool-id $POOL --username tienda-vlc-003 --group-name tiendas
aws cognito-idp admin-get-user --user-pool-id $POOL --username tienda-vlc-003 --query UserStatus --output text   # CONFIRMED
```

### 4. API REST con `GET /hola` e integración mock

1. **API Gateway → APIs → Create API → REST API → Build.** No la tarjeta *REST API Private*. Nombre: `curso-hola`. Tipo de endpoint: *Regional*.
2. **Resources → Create resource:** nombre `hola`.
3. Selecciona `/hola` → **Create method:** **Method type** `GET`, **Integration type** *Mock*. **Create method.**
4. Opcional, para ver el usuario en la respuesta: **Integration response → Edit →** plantilla de mapeo `application/json`, con el contenido de `application/json` en `ejercicio-f-cognito/cli/respuesta.json`. Sin plantilla, responde 200 con el cuerpo vacío.

```bash
API=$(aws apigateway create-rest-api --name curso-hola$S --endpoint-configuration types=REGIONAL --query id --output text)
RAIZ=$(aws apigateway get-resources --rest-api-id $API --query 'items[?path==`/`].id' --output text)
RECURSO=$(aws apigateway create-resource --rest-api-id $API --parent-id $RAIZ --path-part hola --query id --output text)
aws apigateway put-method --rest-api-id $API --resource-id $RECURSO --http-method GET --authorization-type NONE
aws apigateway put-integration --rest-api-id $API --resource-id $RECURSO --http-method GET --type MOCK \
  --request-templates file://ejercicio-f-cognito/cli/peticion.json
aws apigateway put-method-response --rest-api-id $API --resource-id $RECURSO --http-method GET --status-code 200
aws apigateway put-integration-response --rest-api-id $API --resource-id $RECURSO --http-method GET --status-code 200 \
  --response-templates file://ejercicio-f-cognito/cli/respuesta.json
```

### 5. Autorizador Cognito en el método

1. **Authorizers → Create authorizer:** nombre `cognito-tiendas`, **Authorizer type** *Cognito*, **Cognito user pool** `tiendas`, **Token source** `Authorization`. **Create authorizer.**
2. **Resources →** `GET` **→ Method request → Edit → Authorization:** `cognito-tiendas`. **Save.**

```bash
POOL_ARN=$(aws cognito-idp describe-user-pool --user-pool-id $POOL --query UserPool.Arn --output text)
AUTORIZADOR=$(aws apigateway create-authorizer --rest-api-id $API --name cognito-tiendas --type COGNITO_USER_POOLS \
  --provider-arns $POOL_ARN --identity-source method.request.header.Authorization --query id --output text)
aws apigateway update-method --rest-api-id $API --resource-id $RECURSO --http-method GET --patch-operations \
  op=replace,path=/authorizationType,value=COGNITO_USER_POOLS op=replace,path=/authorizerId,value=$AUTORIZADOR
```

### 6. Desplegar en la etapa `prod`

**Resources → Deploy API:** *New stage*, nombre `prod`. **Deploy.** Copia la **Invoke URL** y añádele `/hola`.

```bash
aws apigateway create-deployment --rest-api-id $API --stage-name prod
URL=https://$API.execute-api.eu-west-1.amazonaws.com/prod/hola
```

## Fase 1 con la CLI

Son los comandos de arriba, en ese orden, desde la **raíz del repositorio**. Antes:

```bash
export AWS_PROFILE=default AWS_REGION=eu-west-1   # o el perfil que uses
S=""                   # sufijo de los nombres: "-cli" si ya está desplegado el módulo de Terraform
read -rs PASSWORD      # 8 caracteres, con mayúscula, minúscula, número y símbolo
```

### En PowerShell

Sin probar. Cambian las variables, las comillas y la continuación de línea:

```powershell
$env:AWS_PROFILE="default"; $env:AWS_REGION="eu-west-1"; $S=""   # o el perfil que uses
$PASSWORD = Read-Host "Contraseña" -MaskInput
$POOL = aws cognito-idp create-user-pool --pool-name "tiendas$S" --query UserPool.Id --output text
$CLIENT_ID = aws cognito-idp create-user-pool-client --user-pool-id $POOL --client-name "curso-hola$S" --no-generate-secret --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH --query UserPoolClient.ClientId --output text
aws cognito-idp create-group --user-pool-id $POOL --group-name tiendas
aws cognito-idp admin-create-user --user-pool-id $POOL --username tienda-vlc-003 --message-action SUPPRESS
aws cognito-idp admin-set-user-password --user-pool-id $POOL --username tienda-vlc-003 --password $PASSWORD --permanent
aws cognito-idp admin-add-user-to-group --user-pool-id $POOL --username tienda-vlc-003 --group-name tiendas
$API = aws apigateway create-rest-api --name "curso-hola$S" --endpoint-configuration types=REGIONAL --query id --output text
$RAIZ = aws apigateway get-resources --rest-api-id $API --query "items[?path=='/'].id" --output text
$RECURSO = aws apigateway create-resource --rest-api-id $API --parent-id $RAIZ --path-part hola --query id --output text
aws apigateway put-method --rest-api-id $API --resource-id $RECURSO --http-method GET --authorization-type NONE
aws apigateway put-integration --rest-api-id $API --resource-id $RECURSO --http-method GET --type MOCK --request-templates file://ejercicio-f-cognito/cli/peticion.json
aws apigateway put-method-response --rest-api-id $API --resource-id $RECURSO --http-method GET --status-code 200
aws apigateway put-integration-response --rest-api-id $API --resource-id $RECURSO --http-method GET --status-code 200 --response-templates file://ejercicio-f-cognito/cli/respuesta.json
$POOL_ARN = aws cognito-idp describe-user-pool --user-pool-id $POOL --query UserPool.Arn --output text
$AUTORIZADOR = aws apigateway create-authorizer --rest-api-id $API --name cognito-tiendas --type COGNITO_USER_POOLS --provider-arns $POOL_ARN --identity-source method.request.header.Authorization --query id --output text
aws apigateway update-method --rest-api-id $API --resource-id $RECURSO --http-method GET --patch-operations op=replace,path=/authorizationType,value=COGNITO_USER_POOLS "op=replace,path=/authorizerId,value=$AUTORIZADOR"
aws apigateway create-deployment --rest-api-id $API --stage-name prod
$URL = "https://$API.execute-api.eu-west-1.amazonaws.com/prod/hola"
```

## Fase 1 con Terraform (plan B)

```bash
cd ejercicio-f-cognito/infra
terraform init && terraform apply     # 12 recursos
cd ../..
python ejercicio-f-cognito/scripts/crear_usuario.py    # pide la contraseña
```

---

## Fase 2: probar con la CLI y curl

```bash
curl -i $URL                                                  # 401 {"message":"Unauthorized"}
ID_TOKEN=$(aws cognito-idp initiate-auth --auth-flow USER_PASSWORD_AUTH --client-id $CLIENT_ID \
  --auth-parameters USERNAME=tienda-vlc-003,PASSWORD="$PASSWORD" --query AuthenticationResult.IdToken --output text)
curl -i -H "Authorization: $ID_TOKEN" $URL                    # 200
```
```powershell
# Sin probar
curl.exe -i $URL
$ID_TOKEN = aws cognito-idp initiate-auth --auth-flow USER_PASSWORD_AUTH --client-id $CLIENT_ID --auth-parameters "USERNAME=tienda-vlc-003,PASSWORD=$PASSWORD" --query AuthenticationResult.IdToken --output text
curl.exe -i -H "Authorization: $ID_TOKEN" $URL
```

**Decodificar el token, en local.** No lo pegues en una web de terceros: un token vigente da acceso a la API hasta que caduca. Hay dos formas, sin dependencias nuevas:

```bash
python ejercicio-f-cognito/scripts/probar_api.py --decodificar "$ID_TOKEN"
python -c "import sys,json,base64; p=sys.argv[1].split('.')[1]; print(json.dumps(json.loads(base64.urlsafe_b64decode(p+'='*(-len(p)%4))),indent=2))" "$ID_TOKEN"
```

Busca `"cognito:groups": ["tiendas"]`. Esto **no verifica la firma**: sirve para mirar el token, no para confiar en él. La firma la comprueba API Gateway.

### Comprobar todo de una vez

Con lo montado a mano:

```bash
python ejercicio-f-cognito/scripts/probar_api.py --url $URL --client-id $CLIENT_ID
```

Con el módulo de Terraform, sin argumentos. Opciones: `--usuario`, `--region`, y la contraseña en `PASSWORD_TIENDA` o por teclado.

**Salida esperada:**

```
Sin token: HTTP 401 {"message":"Unauthorized"}
Con token: HTTP 200 {
  "mensaje": "Hola desde la API protegida",
  "usuario": "tienda-vlc-003",
  "grupos": "tiendas"
}
Payload del ID token (sin verificar la firma):
{
  "sub": "02d554b4-...",
  "cognito:groups": ["tiendas"],
  "token_use": "id",
  "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_...",
  "exp": 1793540059
}
Criterios de aceptación
  [OK] 401 sin token
  [OK] 200 con token
  [OK] Grupo tiendas en el token
Terminado (401 sin token y 200 con token): SÍ
```

## Errores típicos

Todos provocados contra AWS, salvo que se indique.

| Síntoma | Causa | Solución |
|---|---|---|
| **Sin token sigue dando 200** | **No has vuelto a desplegar** tras añadir el autorizador. En la prueba: 200 con el autorizador añadido, y 401 tras desplegar | **Deploy API**, o `create-deployment` |
| `NotAuthorizedException: Client ... is configured with secret but SECRET_HASH was not received` | **App client con secret** | El secret no se puede quitar: crea otro cliente sin secret. En el asistente, elige SPA |
| `initiate-auth` no devuelve tokens, sino `ChallengeName: NEW_PASSWORD_REQUIRED`. Con `--query AuthenticationResult.IdToken` sale `None` | **Usuario en `FORCE_CHANGE_PASSWORD`** | `admin-set-user-password --permanent`. `probar_api.py` lo explica |
| 401 con el token correcto | Has enviado el **access token** | Sin scopes en el método, usa el **ID token**. Comprobado: access 401, ID 200 |
| No aparece `cognito:groups` en el token | El usuario no está en el grupo, o el token es anterior | `admin-add-user-to-group` y pide otro token. *Sin provocar* |
| `USER_PASSWORD_AUTH flow not enabled for this client` | Falta `ALLOW_USER_PASSWORD_AUTH` en el app client | Paso 2. *Sin provocar: el mensaje es de memoria* |

## Qué contar

- **El prefijo `Bearer` también funciona** en este autorizador: 200 con y sin él, según la prueba. La documentación solo dice que el token va en `Authorization`.
- **ID token frente a access token.** Sin scopes en el método, API Gateway trata lo recibido como ID token; con scopes, como access token. Por eso aquí el access token da 401.
- **Decodificar no es verificar.** El contenido de un JWT es legible por cualquiera.
- **`USER_PASSWORD_AUTH` es para este laboratorio:** la contraseña viaja al servicio, cifrada por TLS. La documentación recomienda el flujo SRP, más seguro, en cuanto termina una migración de usuarios.
- **Una API REST no publica sus cambios hasta desplegarla.**

## Limpieza

**A mano:**

- **Consola:** **API Gateway → APIs →** `curso-hola` **→ API actions → Delete API**. **Cognito → User pools →** `tiendas` **→ Delete user pool**. Borra también el usuario, el grupo y el cliente.
- **CLI:**

  ```bash
  aws apigateway delete-rest-api --rest-api-id $API
  aws cognito-idp delete-user-pool --user-pool-id $POOL
  ```

**Con Terraform:**

```bash
cd ejercicio-f-cognito/infra && terraform destroy && cd ../..
```
