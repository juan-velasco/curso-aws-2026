# Handoff: ajustes del ejercicio F (Cognito) · Curso AWS para HP

> **Para el profesor.** Copia este fichero en la raíz del repositorio como `HANDOFF_EJERCICIO_F.md` y pide a Claude Code: *«Lee HANDOFF_EJERCICIO_F.md y ESTADO_SESION3.md y haz los ajustes. Pregúntame antes de cualquier acción que cree, modifique o borre recursos en AWS»*.

---

## 1. Contexto

El ejercicio F ya está implementado y probado en `ejercicio-f-cognito/`: Terraform (user pool, app client, grupo, API REST con mock y autorizador Cognito), `crear_usuario.py`, `probar_api.py` y `SOLUCION.md` (ver `ESTADO_SESION3.md`).

El profesor ha rehecho las diapositivas de Cognito (64 a 75). El ejercicio queda planteado así:

- **Fase 1 · Montar en la consola de AWS:**
  - user pool `tiendas` con inicio de sesión por nombre de usuario;
  - app client público, sin secret, con `ALLOW_USER_PASSWORD_AUTH`;
  - usuario de prueba con contraseña permanente, dentro del grupo `tiendas`;
  - API REST con `GET /hola` (integración mock) y autorizador Cognito en el método;
  - despliegue en la etapa `prod`.
- **Fase 2 · Probar con la CLI y curl:**
  - llamar sin token y obtener 401;
  - pedir los tokens con `initiate-auth` y copiar el `IdToken`;
  - llamar con la cabecera `Authorization` y obtener 200;
  - decodificar el token y localizar `cognito:groups`.
- **Terminado cuando** la misma URL da 401 sin token y 200 con token.

Es decir, **los alumnos lo hacen a mano**. El código del repositorio pasa a ser la **solución de referencia y el plan B** (para el profesor o para un alumno que se atasque), y las herramientas de prueba tienen que servir también para lo montado a mano.

No hay que reescribir el ejercicio: solo ajustarlo y comprobar cuatro dudas de las diapositivas.

---

## 2. Cambios en el código

1. **`probar_api.py` para lo montado a mano.**
   - Además de leer los outputs de Terraform (comportamiento actual, por defecto), debe aceptar `--url`, `--client-id`, `--usuario` y la contraseña por variable de entorno o petición interactiva.
   - Así un alumno que lo montó en la consola puede comprobar su ejercicio.
   - Al final, muestra el criterio de terminado: «401 sin token y 200 con token».
2. **Decodificar en local.** Las diapositivas proponen jwt.io. Pegar un token real en una web de terceros es una mala práctica que conviene no enseñar.
   - `probar_api.py` ya decodifica en local: añade la opción `--decodificar <token>` para usarlo solo con eso.
   - Incluye en `SOLUCION.md` un comando equivalente de una línea con Python, sin dependencias.
3. **`SOLUCION.md` como guion de la Fase 1:**
   - Pasos de consola numerados y con el orden de las diapositivas. **Compruébalos en la consola actual**: si no puedes navegarla, indícalo y verifica al menos con la CLI que cada opción existe con ese nombre.
   - Para cada paso, el comando de CLI equivalente.
   - Errores típicos:
     - no volver a desplegar tras añadir el autorizador;
     - app client con secret;
     - usuario en `FORCE_CHANGE_PASSWORD`.
   - Limpieza manual al terminar: borrar la API y el user pool.
4. **Prueba de la CLI de `SOLUCION.md`.** Ejecuta la secuencia de comandos de CLI completa en una cuenta limpia de nombres, con un sufijo para no chocar con el módulo de Terraform, comprueba 401 y 200, y bórralo todo. Hasta ahora esos comandos no se han lanzado (`ESTADO_SESION3.md`).

---

## 3. Dudas de las diapositivas que hay que comprobar contra AWS

Con la API del módulo de Terraform, anota el resultado de cada prueba en `CAMBIOS_DIAPOSITIVAS.md`:

| # | Diapositiva | Qué dice | Qué probar |
|---|---|---|---|
| 1 | 68 · Cómo se usa el token | El ejemplo envía `Authorization: Bearer eyJ…` | El autorizador Cognito de una API REST con `Bearer ` delante del token: ¿200 o 401? En la sesión 3 se probó sin `Bearer` (200). Si con `Bearer` da 401, la diapositiva debe aclarar que el prefijo es para HTTP API, ALB o validación en la aplicación |
| 2 | 69 · Tres formas de proteger una API | «Autoriza con el access token. El Cognito authorizer de REST API sin scopes también acepta el ID token» | Llamar con el **access token** al método sin scopes: ¿200 o 401? Si da 401, el texto debe decir que sin scopes se usa el ID token y que el access token requiere scopes en el método |
| 3 | 70 · Cómo se obtiene el token | `USER_PASSWORD_AUTH` aparece «para migrar usuarios» | Sin prueba: confirma en la documentación si conviene añadir «y laboratorios» o similar, porque es el flujo del ejercicio |
| 4 | 67 · Precios | Plan **Essentials** por defecto | Comprueba qué plan crea el módulo de Terraform y qué plan propone la consola al crear un pool nuevo. Si Essentials no aporta nada al ejercicio, valora fijar **Lite** en Terraform. Ambos tienen 10.000 MAU gratis: es por coherencia, no por coste |

---

## 4. Reglas y entrega

- **Pregunta antes** de crear o borrar recursos en AWS. Lo creado en la prueba de §2.4 se borra al terminar, y lo indicas.
- No cambies los nombres del módulo de Terraform (`tiendas`, `curso-hola`, `tienda-vlc-003`): los usan las diapositivas.
- `pytest`, `ruff` y `terraform validate` en verde. Añade tests para los argumentos nuevos de `probar_api.py` y para `--decodificar`.
- Actualiza `ESTADO_SESION3.md` (fila del ejercicio F) y añade a `CAMBIOS_DIAPOSITIVAS.md`, sección «Sesión 3», los resultados de §3 y cualquier diferencia con las diapositivas 73 a 75.
