# Solución · Ejercicio F: proteger una API con Cognito

**Probado contra AWS** el 01-11-2026: 401 sin token, 200 con token y grupo `tiendas` en el token. **Coste:** sin coste por hora; una API sin tráfico y un user pool con un usuario quedan dentro del nivel gratuito.

## Con Terraform y los scripts

```bash
cd ejercicio-f-cognito/infra
terraform init && terraform apply     # 12 recursos
cd ../..
python ejercicio-f-cognito/scripts/crear_usuario.py    # pide la contraseña
python ejercicio-f-cognito/scripts/probar_api.py
```

Para no teclear la contraseña, usa la variable de entorno `PASSWORD_TIENDA`. **Nunca va en un fichero.** Política por defecto: 8 caracteres, con mayúscula, minúscula, número y símbolo.

**Salida esperada de `probar_api.py`:**

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
```

## La solución, pieza a pieza

| Pieza | Decisión | Terraform | CLI equivalente |
|---|---|---|---|
| User pool `tiendas` | Inicio de sesión por nombre de usuario, sin MFA | `aws_cognito_user_pool.tiendas` | `aws cognito-idp create-user-pool --pool-name tiendas` |
| App client | Público, sin secreto, con `ALLOW_USER_PASSWORD_AUTH` y `ALLOW_REFRESH_TOKEN_AUTH` | `aws_cognito_user_pool_client.api` | `aws cognito-idp create-user-pool-client --user-pool-id $POOL --client-name curso-hola --no-generate-secret --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH` |
| Grupo `tiendas` | | `aws_cognito_user_group.tiendas` | `aws cognito-idp create-group --user-pool-id $POOL --group-name tiendas` |
| Usuario | Estado `CONFIRMED`, sin cambio de contraseña pendiente | `crear_usuario.py` | `admin-create-user`, `admin-set-user-password --permanent` y `admin-add-user-to-group` |
| API REST `curso-hola` | Recurso `GET /hola` con integración mock | `aws_api_gateway_rest_api`, `_resource`, `_method`, `_integration` | `aws apigateway create-rest-api --name curso-hola`, `create-resource`, `put-method`, `put-integration --type MOCK` |
| Autorizador | Tipo Cognito, sobre la cabecera `Authorization`; método con `COGNITO_USER_POOLS` | `aws_api_gateway_authorizer.cognito` | `aws apigateway create-authorizer --type COGNITO_USER_POOLS --provider-arns $ARN --identity-source method.request.header.Authorization` |
| Despliegue | Etapa `prod` | `aws_api_gateway_deployment`, `aws_api_gateway_stage` | `aws apigateway create-deployment --rest-api-id $API --stage-name prod` |

**En la consola:** Cognito → *Create user pool*; API Gateway → *REST API* → *Create resource* → *Create method* (tipo *Mock*) → *Authorizers* → *Deploy API*. **Comandos y consola no se han probado a mano:** lo probado es Terraform con los scripts.

## Paso a paso con la CLI (diapositiva 67)

```bash
aws cognito-idp initiate-auth --auth-flow USER_PASSWORD_AUTH --client-id $CLIENT_ID \
  --auth-parameters USERNAME=tienda-vlc-003,PASSWORD=$PASSWORD
curl -i $URL_API                                    # 401
curl -i -H "Authorization: $ID_TOKEN" $URL_API      # 200
```

`terraform output` da `client_id` y `url_api`.

## Qué contar

- **El ID token, sin `Bearer`.** El autorizador de Cognito acepta el token tal cual en la cabecera.
- **Decodificar no es verificar.** `probar_api.py` lee el contenido sin comprobar la firma. Es API Gateway quien la verifica.
- **`USER_PASSWORD_AUTH` es solo para laboratorio:** la contraseña llega al servicio. En producción, SRP o el flujo con Hosted UI.
- **Una API REST no publica sus cambios hasta desplegarla.** Sin un despliegue nuevo, la etapa sigue con la versión anterior.

## Limpieza

```bash
cd ejercicio-f-cognito/infra && terraform destroy && cd ../..
```

Borra también el usuario, que está dentro del user pool. Sin coste si se deja.
