# Guion · Demo 2: CDC de clientes con DMS

**Flujo:** RDS PostgreSQL (`clientes`, `productos`) → AWS DMS (Full load + CDC) → S3 `bronze/cdc/public/<tabla>/` en Parquet
**Duración:** ~25 min de demo, más **≈ 10 min de creación** de la infraestructura, que conviene lanzar **antes de empezar la explicación** de DMS.
**Coste:** ≈ 0,06 USD/h mientras exista: RDS `db.t4g.micro` (0,017 USD/h), `dms.t3.small` (0,039 USD/h) y el secreto (0,40 USD/mes, prorrateado). **Se destruye al terminar.**
**Requisitos:** `infra/base` aplicado y entorno de Python con `requirements.txt` activado.

**En cada terminal nueva:** define el perfil y la región ([cómo](../README.md#preparar-la-terminal)). Todos los comandos se lanzan desde la **raíz del repositorio**.

**Repetir la demo en una cuenta que ya tiene las demos 3 y 4 cambia sus resultados:** añade otra carga completa y otros cambios a `bronze/cdc/`, y las cifras y versiones que muestran sus guiones dejan de coincidir.

---

## 0. Antes de clase: lanzar la infraestructura (≈ 10 min, en segundo plano)

```bash
cd demo2-cdc-dms/infra
terraform init
terraform apply          # 31 recursos: RDS ≈ 6 min, instancia de DMS ≈ 8 min (en paralelo)
cd ../..
```

Crea VPC (dos subredes públicas, sin NAT), RDS, parameter group, Secrets Manager, roles IAM, instancia de replicación, endpoints y tarea (sin arrancar).

**Si falla:**
- `EntityAlreadyExists: Role with name dms-vpc-role already exists`: los roles de cuenta de DMS ya existen. Pon `crear_roles_dms = false` en `terraform.tfvars` y repite.
- `The IAM Role arn:aws:iam::…:role/dms-vpc-role is not configured properly` al crear el subnet group: el rol se acaba de crear y aún no ha propagado. Repite `terraform apply` al cabo de un minuto.
- Error en el security group con la IP: la detección automática ha fallado (proxy). Pon `mi_ip = "x.x.x.x"` en `terraform.tfvars`.

## 1. RDS PostgreSQL db.t4g.micro con `rds.logical_replication = 1` (≈ 2 min)

```bash
terraform -chdir=demo2-cdc-dms/infra output psql
```

Consola: **RDS → curso-aws-hp-retail → Configuration**: parameter group `curso-aws-hp-pg17-cdc` con `rds.logical_replication = 1` y `wal_sender_timeout = 0`.

**Qué contar:** DMS lee el WAL con replicación lógica (`wal_level = logical`). Es un parámetro estático y, en una instancia existente, exige reiniciar. Las claves primarias son imprescindibles para replicar bien los UPDATE y DELETE.

## 2. Semilla: 4.000 clientes y 1.200 productos (≈ 1 min)

```bash
python demo2-cdc-dms/scripts/cargar_semilla.py
```

**Salida esperada:**

```
wal_level = logical
Esquema creado (clientes, productos)
Usuario dms_user creado con rds_replication y SELECT sobre public
clientes: 4000 filas cargadas
productos: 1200 filas cargadas

Total: 4000 clientes, 1200 productos. C-17: ('Standard', 'Valencia')
```

Es idempotente: si se repite, avisa y no duplica. Los datos salen de `comun/maestros.py`, igual que en el generador de la demo 1.

**Si falla:**
- `wal_level = replica` (con AVISO): reinicia la instancia con `aws rds reboot-db-instance --db-instance-identifier curso-aws-hp-retail --region eu-west-1`, espera a `available` y repite.
- `connection timeout`: tu IP ha cambiado (wifi distinta). Haz `terraform apply` en `demo2-cdc-dms/infra` para actualizar el security group.

## 3. Endpoints con el secreto de Secrets Manager y prueba de conexión (≈ 3 min)

Consola: **DMS → Endpoints**:
- `curso-aws-hp-postgres` (origen): credenciales en el secreto `curso-aws-hp/demo2/dms-user` (claves `username`, `password`, `host`, `port`), SSL `require`, usuario `dms_user` (no el maestro).
- `curso-aws-hp-bronze-cdc` (destino S3): carpeta `bronze/cdc`, Parquet, columna `ts_commit`, particiones por fecha `AAAA/MM/DD`, lotes CDC cada 60 s como máximo.

```bash
python demo2-cdc-dms/scripts/tarea_dms.py probar
```

**Salida esperada** (1–2 min):

```
  [OK] destino (S3): successful
  [OK] origen (PostgreSQL): successful
```

**Si falla:** el origen con `password authentication failed` indica que la semilla no se ha ejecutado (no existe `dms_user`).

## 4. Tarea Full load + CDC hacia bronze en Parquet (≈ 3 min)

```bash
python demo2-cdc-dms/scripts/tarea_dms.py iniciar
python demo2-cdc-dms/scripts/tarea_dms.py estado
```

**Salida esperada** (al cabo de ~1 min):

```
Tarea curso-aws-hp-clientes-productos: running
  Carga completa: 100 %, tablas cargadas 2, con error 0
  tabla             estado                      carga   ins   upd   del
  public.clientes   Table completed              4000     0     0     0
  public.productos  Table completed              1200     0     0     0
```

```bash
python demo2-cdc-dms/scripts/comprobar_cdc.py
```

Muestra los ficheros `LOAD00000001.parquet` de cada tabla (directamente en `bronze/cdc/public/<tabla>/`, sin carpeta de fecha), con 4.000 y 1.200 filas y **sin columna `Op`**.

## 5. UPDATE del segmento de C-17 y localizar el fichero CDC en S3 (≈ 4 min)

```bash
python demo2-cdc-dms/scripts/aplicar_cambios.py
```

Ejecuta `sql/03_cambios_demo.sql` en una transacción: `UPDATE` de C-17 a `Premium`, `INSERT` de C-4001 (`Standard`, Lyon, FR) y `DELETE` de C-981. Para hacerlo a mano con `psql`:

```bash
export PGPASSWORD=$(terraform -chdir=demo2-cdc-dms/infra output -raw password_maestra)
eval $(terraform -chdir=demo2-cdc-dms/infra output -raw psql)
```
```powershell
$env:PGPASSWORD = terraform -chdir=demo2-cdc-dms/infra output -raw password_maestra
Invoke-Expression (terraform -chdir=demo2-cdc-dms/infra output -raw psql)
```

Al cabo de **~1 minuto** (intervalo máximo del lote CDC):

```bash
python demo2-cdc-dms/scripts/comprobar_cdc.py
```

**Salida esperada:**

```
  CDC clientes/2026/10/28/20261028-172434489.parquet  (3 filas)
    Op=U  cliente_id=C-17  segmento=Premium  provincia=Valencia  ts_commit=2026-10-28 17:23:34.470161
    Op=I  cliente_id=C-4001  segmento=Standard  provincia=Lyon  ts_commit=2026-10-28 17:23:34.470161
    Op=D  cliente_id=C-981  segmento=Standard  provincia=Madrid  ts_commit=2026-10-28 17:23:34.470161

Criterios de aceptación
  [OK] LOAD de clientes con 4000 filas y sin columna Op ...
  [OK] Ficheros CDC de clientes en carpetas AAAA/MM/DD/
  [OK] U de C-17 (Premium) con ts_commit
  [OK] I de C-4001 (Standard) con ts_commit
  [OK] D de C-981 con ts_commit
```

Medido en la prueba: el fichero CDC apareció **61 s** después del `COMMIT`. Los tres cambios comparten `ts_commit` porque van en la misma transacción.

**Qué contar:** bronze guarda la historia de los cambios, no el estado actual. En la sesión 2 se reconstruye el estado en silver (la última versión por `cliente_id` según `ts_commit`, quitando las `D`). Con `REPLICA IDENTITY FULL` el `D` lleva la fila completa, no solo la clave. Ojo: `ts_commit` es una columna **string** (`AAAA-MM-DD HH:MM:SS.ffffff`); las fechas propias de las tablas (`actualizado_en`, `fecha_alta`) sí son `timestamp[ms]`.

**Para repetir la demo:** C-17 ya es `Premium` y C-981 ya no existe. Para volver al estado inicial, destruye y recrea el módulo, o revierte a mano con `psql`.

## 6. Parar la tarea y la instancia de replicación al terminar (≈ 2 min + destroy)

```bash
python demo2-cdc-dms/scripts/tarea_dms.py parar        # espera a 'stopped'
cd demo2-cdc-dms/infra
terraform destroy                                       # ≈ 10 min
```

---

## Limpieza (checklist de la diapositiva)

- [x] La tarea de DMS se para (`tarea_dms.py parar`) y la **instancia de replicación se borra** (`terraform destroy`).
- [x] **RDS se destruye con el módulo.** Detenerla no basta: AWS reinicia una RDS detenida a los 7 días y vuelve a cobrar.
- [x] Firehose y bucket **se mantienen** (los datos de `bronze/cdc/` se quedan para la sesión 2).
- [x] `docker compose down` en `demo1-ingesta`.

Comprobación de que no queda nada de la demo 2:

```bash
aws resourcegroupstaggingapi get-resources --tag-filters Key=demo,Values=demo2 --region eu-west-1 --query "ResourceTagMappingList[].ResourceARN"
```

Si `terraform destroy` falla en la instancia de replicación porque la tarea está en marcha, ejecuta `tarea_dms.py parar` y repite.
