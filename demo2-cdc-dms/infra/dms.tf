data "aws_caller_identity" "actual" {}

# --- Roles de cuenta que DMS necesita con estos nombres exactos ------------------
# Pueden existir ya en una cuenta de empresa: en ese caso, crear_roles_dms = false.

data "aws_iam_policy_document" "dms_confianza" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["dms.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "dms_vpc" {
  count              = var.crear_roles_dms ? 1 : 0
  name               = "dms-vpc-role"
  assume_role_policy = data.aws_iam_policy_document.dms_confianza.json
}

resource "aws_iam_role_policy_attachment" "dms_vpc" {
  count      = var.crear_roles_dms ? 1 : 0
  role       = aws_iam_role.dms_vpc[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonDMSVPCManagementRole"
}

resource "aws_iam_role" "dms_logs" {
  count              = var.crear_roles_dms ? 1 : 0
  name               = "dms-cloudwatch-logs-role"
  assume_role_policy = data.aws_iam_policy_document.dms_confianza.json
}

resource "aws_iam_role_policy_attachment" "dms_logs" {
  count      = var.crear_roles_dms ? 1 : 0
  role       = aws_iam_role.dms_logs[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonDMSCloudWatchLogsRole"
}

# --- Secreto del usuario de DMS -------------------------------------------------------

resource "random_password" "dms_user" {
  length  = 24
  special = false
}

resource "aws_secretsmanager_secret" "dms_user" {
  name                    = "curso-aws-hp/demo2/dms-user"
  description             = "Credenciales del usuario dms_user en RDS PostgreSQL (origen de DMS)"
  recovery_window_in_days = 0 # borrado inmediato en destroy: el nombre se puede reutilizar
}

# Claves que espera DMS para PostgreSQL
resource "aws_secretsmanager_secret_version" "dms_user" {
  secret_id = aws_secretsmanager_secret.dms_user.id
  secret_string = jsonencode({
    username = "dms_user"
    password = random_password.dms_user.result
    host     = aws_db_instance.retail.address
    port     = aws_db_instance.retail.port
  })
}

data "aws_iam_policy_document" "dms_secreto_confianza" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type = "Service"
      # DMS asume el rol de acceso a Secrets Manager con el principal regional
      identifiers = ["dms.amazonaws.com", "dms.${local.region}.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "dms_secreto" {
  statement {
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = [aws_secretsmanager_secret.dms_user.arn]
  }
}

resource "aws_iam_role" "dms_secreto" {
  name               = "curso-aws-hp-dms-secreto"
  assume_role_policy = data.aws_iam_policy_document.dms_secreto_confianza.json
}

resource "aws_iam_role_policy" "dms_secreto" {
  name   = "leer-secreto-dms-user"
  role   = aws_iam_role.dms_secreto.id
  policy = data.aws_iam_policy_document.dms_secreto.json
}

# --- Rol de DMS para escribir en bronze/cdc/ -------------------------------------------

data "aws_iam_policy_document" "dms_s3" {
  statement {
    sid       = "Bucket"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [local.bucket_arn]
  }

  statement {
    sid       = "Objetos"
    actions   = ["s3:PutObject", "s3:DeleteObject", "s3:PutObjectTagging", "s3:GetObject"]
    resources = ["${local.bucket_arn}/bronze/cdc/*"]
  }
}

resource "aws_iam_role" "dms_s3" {
  name               = "curso-aws-hp-dms-s3"
  assume_role_policy = data.aws_iam_policy_document.dms_confianza.json
}

resource "aws_iam_role_policy" "dms_s3" {
  name   = "escritura-bronze-cdc"
  role   = aws_iam_role.dms_s3.id
  policy = data.aws_iam_policy_document.dms_s3.json
}

# --- Logs de las tareas de DMS ------------------------------------------------------------
# Sin declararlo, DMS lo crea por su cuenta y terraform destroy no lo borra. El nombre
# lo fija DMS: dms-tasks-<id de la instancia de replicación>.

resource "aws_cloudwatch_log_group" "dms_tareas" {
  name              = "dms-tasks-curso-aws-hp-demo2"
  retention_in_days = 7
}

# --- Instancia de replicación -------------------------------------------------------------

resource "aws_dms_replication_subnet_group" "demo2" {
  replication_subnet_group_id          = "curso-aws-hp-demo2"
  replication_subnet_group_description = "Subredes publicas de la demo 2"
  subnet_ids                           = aws_subnet.publica[*].id

  # DMS valida dms-vpc-role al crear el subnet group
  depends_on = [aws_iam_role_policy_attachment.dms_vpc]
}

resource "aws_dms_replication_instance" "demo2" {
  replication_instance_id     = "curso-aws-hp-demo2"
  replication_instance_class  = var.clase_dms
  engine_version              = var.version_dms
  allocated_storage           = 50 # GB incluidos en el precio de la instancia
  multi_az                    = false
  publicly_accessible         = true # llega a Secrets Manager sin endpoints de interfaz (de pago)
  replication_subnet_group_id = aws_dms_replication_subnet_group.demo2.id
  vpc_security_group_ids      = [aws_security_group.dms.id]
  apply_immediately           = true
  auto_minor_version_upgrade  = false

  depends_on = [aws_iam_role_policy_attachment.dms_logs]
}

# --- Endpoints ---------------------------------------------------------------------------------

resource "aws_dms_endpoint" "origen" {
  endpoint_id   = "curso-aws-hp-postgres"
  endpoint_type = "source"
  engine_name   = "postgres"
  database_name = local.db_name
  ssl_mode      = "require"

  secrets_manager_arn             = aws_secretsmanager_secret.dms_user.arn
  secrets_manager_access_role_arn = aws_iam_role.dms_secreto.arn

  postgres_settings {
    # dms_user no es superusuario: sin captura de DDL no hacen falta
    # la tabla awsdms_ddl_audit ni el event trigger en la base de datos
    capture_ddls = false
  }

  depends_on = [aws_secretsmanager_secret_version.dms_user, aws_iam_role_policy.dms_secreto]
}

resource "aws_dms_s3_endpoint" "bronze" {
  endpoint_id             = "curso-aws-hp-bronze-cdc"
  endpoint_type           = "target"
  bucket_name             = local.bucket_name
  bucket_folder           = "bronze/cdc" # -> bronze/cdc/public/clientes/, bronze/cdc/public/productos/
  service_access_role_arn = aws_iam_role.dms_s3.arn

  data_format                      = "parquet"
  parquet_version                  = "parquet-2-0"
  parquet_timestamp_in_millisecond = true # compatibilidad con Athena
  timestamp_column_name            = "ts_commit"
  include_op_for_full_load         = false # la carga inicial no lleva Op
  encryption_mode                  = "SSE_S3"
  date_partition_enabled           = true
  date_partition_sequence          = "YYYYMMDD"
  date_partition_delimiter         = "SLASH" # .../AAAA/MM/DD/
  cdc_max_batch_interval           = 60      # segundos: los cambios aparecen rápido en la demo

  depends_on = [aws_iam_role_policy.dms_s3]
}

# --- Tarea de replicación ---------------------------------------------------------------------

resource "aws_dms_replication_task" "clientes_productos" {
  replication_task_id      = "curso-aws-hp-clientes-productos"
  migration_type           = "full-load-and-cdc"
  replication_instance_arn = aws_dms_replication_instance.demo2.replication_instance_arn
  source_endpoint_arn      = aws_dms_endpoint.origen.endpoint_arn
  target_endpoint_arn      = aws_dms_s3_endpoint.bronze.endpoint_arn
  start_replication_task   = false # se arranca en la demo: scripts/tarea_dms.py iniciar

  table_mappings = jsonencode({
    rules = [
      for i, tabla in ["clientes", "productos"] : {
        rule-type   = "selection"
        rule-id     = tostring(i + 1)
        rule-name   = "incluir-${tabla}"
        rule-action = "include"
        object-locator = {
          schema-name = "public"
          table-name  = tabla
        }
      }
    ]
  })

  replication_task_settings = jsonencode({
    Logging = {
      EnableLogging = true
    }
  })

  lifecycle {
    # DMS completa los ajustes con sus valores por defecto: evitar diferencias perpetuas
    ignore_changes = [replication_task_settings]
  }

  # El log group debe existir antes de que la tarea escriba en él
  depends_on = [aws_cloudwatch_log_group.dms_tareas]
}
