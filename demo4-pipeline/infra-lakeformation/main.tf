# SOLO EL PROFESOR, EN UNA CUENTA DE PRUEBAS. Modo de acceso híbrido: los permisos de Lake
# Formation solo se aplican a los dos roles con opt-in; los jobs de Glue, Redshift y el resto
# de usuarios siguen con IAM.
#
# Este módulo NO declara aws_lakeformation_data_lake_settings. Ese recurso sustituye la
# configuración de toda la cuenta, y su destroy deja administradores y permisos por defecto
# vacíos. Aquí no hace falta: basta con que quien aplica ya sea administrador del lago, y
# la comprobación de abajo lo exige. Así, destroy no toca la configuración de la cuenta.

data "terraform_remote_state" "base" {
  backend = "local"
  config  = { path = "${path.module}/../../infra/base/terraform.tfstate" }
}

data "aws_caller_identity" "actual" {}

data "aws_lakeformation_data_lake_settings" "actual" {}

locals {
  region      = data.terraform_remote_state.base.outputs.region
  bucket_name = data.terraform_remote_state.base.outputs.bucket_name
  bucket_arn  = data.terraform_remote_state.base.outputs.bucket_arn
  account_id  = data.aws_caller_identity.actual.account_id
  profesor    = var.principal_profesor != "" ? var.principal_profesor : data.aws_caller_identity.actual.arn

  roles_demo    = { analista = aws_iam_role.demo["curso-analista-asia"], ciencia = aws_iam_role.demo["curso-data-science"] }
  columnas_pii  = ["nombre", "email", "telefono"]
  tablas_con_lf = ["ventas", "dim_cliente"]
}

resource "terraform_data" "comprobar_administrador" {
  lifecycle {
    precondition {
      condition     = contains(data.aws_lakeformation_data_lake_settings.actual.admins, data.aws_caller_identity.actual.arn)
      error_message = "Quien aplica debe ser administrador del lago. Añádelo en Lake Formation > Administrative roles and tasks, conservando los que ya haya."
    }
  }
}

# --- Ubicación registrada en modo híbrido ---------------------------------------------

data "aws_iam_policy_document" "lf_confianza" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lakeformation.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "lf_acceso" {
  statement {
    actions   = ["s3:ListBucket"]
    resources = [local.bucket_arn]
  }

  statement {
    actions   = ["s3:GetObject"]
    resources = ["${local.bucket_arn}/silver/*"]
  }
}

resource "aws_iam_role" "lf_acceso" {
  name               = "curso-lakeformation-acceso"
  assume_role_policy = data.aws_iam_policy_document.lf_confianza.json
}

resource "aws_iam_role_policy" "lf_acceso" {
  name   = "lectura-silver"
  role   = aws_iam_role.lf_acceso.id
  policy = data.aws_iam_policy_document.lf_acceso.json
}

resource "aws_lakeformation_resource" "silver" {
  arn                   = "${local.bucket_arn}/silver/"
  role_arn              = aws_iam_role.lf_acceso.arn
  hybrid_access_enabled = true

  depends_on = [terraform_data.comprobar_administrador, aws_iam_role_policy.lf_acceso]
}

# --- Roles de la demo: se asumen con switch role desde la consola -------------------------

data "aws_iam_policy_document" "roles_confianza" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [local.profesor]
    }
  }
}

data "aws_iam_policy_document" "roles_demo" {
  statement {
    sid = "Athena"
    actions = [
      "athena:GetWorkGroup",
      "athena:StartQueryExecution",
      "athena:StopQueryExecution",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
      "athena:ListQueryExecutions",
      "athena:BatchGetQueryExecution",
    ]
    resources = ["arn:aws:athena:${local.region}:${local.account_id}:workgroup/curso"]
  }

  statement {
    sid = "ConsolaAthena"
    actions = [
      "athena:ListWorkGroups",
      "athena:ListEngineVersions",
      "athena:ListDataCatalogs",
      "athena:ListDatabases",
      "athena:ListTableMetadata",
      "athena:GetTableMetadata",
    ]
    resources = ["*"]
  }

  statement {
    sid = "GlueLectura"
    actions = [
      "glue:GetCatalog",
      "glue:GetCatalogImportStatus",
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:GetTable",
      "glue:GetTables",
      "glue:GetPartition",
      "glue:GetPartitions",
      "glue:BatchGetPartition",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "DatosPorLakeFormation"
    actions   = ["lakeformation:GetDataAccess"]
    resources = ["*"]
  }

  statement {
    sid       = "ResultadosAthena"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"]
    resources = ["${local.bucket_arn}/athena-results/*"]
  }

  statement {
    sid       = "Bucket"
    actions   = ["s3:GetBucketLocation", "s3:ListBucket", "s3:ListBucketMultipartUploads"]
    resources = [local.bucket_arn]
  }
}

resource "aws_iam_role" "demo" {
  for_each           = toset(["curso-analista-asia", "curso-data-science"])
  name               = each.key
  assume_role_policy = data.aws_iam_policy_document.roles_confianza.json
}

resource "aws_iam_role_policy" "demo" {
  for_each = aws_iam_role.demo
  name     = "athena-curso"
  role     = each.value.id
  policy   = data.aws_iam_policy_document.roles_demo.json
}

# --- LF-Tags ---------------------------------------------------------------------------------

resource "aws_lakeformation_lf_tag" "capa" {
  key        = "capa"
  values     = ["bronze", "silver"]
  depends_on = [terraform_data.comprobar_administrador]
}

resource "aws_lakeformation_lf_tag" "sensibilidad" {
  key        = "sensibilidad"
  values     = ["publico", "pii"]
  depends_on = [terraform_data.comprobar_administrador]
}

# Toda la base de datos es silver y pública; las columnas personales lo sobrescriben
resource "aws_lakeformation_resource_lf_tags" "silver" {
  database {
    name = "silver"
  }

  lf_tag {
    key   = aws_lakeformation_lf_tag.capa.key
    value = "silver"
  }

  lf_tag {
    key   = aws_lakeformation_lf_tag.sensibilidad.key
    value = "publico"
  }
}

resource "aws_lakeformation_resource_lf_tags" "pii" {
  table_with_columns {
    database_name = "silver"
    name          = "dim_cliente"
    column_names  = local.columnas_pii
  }

  lf_tag {
    key   = aws_lakeformation_lf_tag.sensibilidad.key
    value = "pii"
  }

  depends_on = [aws_lakeformation_resource_lf_tags.silver]
}

# --- Filtro de filas y columnas (diapositiva «Filtro de filas y columnas») --------------------

resource "aws_lakeformation_data_cells_filter" "analistas_asia" {
  table_data {
    table_catalog_id = local.account_id
    database_name    = "silver"
    table_name       = "ventas"
    name             = "analistas_asia"

    row_filter {
      filter_expression = "pais IN ('JP', 'CN')"
    }

    column_wildcard {
      excluded_column_names = ["cliente_id"]
    }
  }

  depends_on = [terraform_data.comprobar_administrador]
}

# --- Permisos ----------------------------------------------------------------------------------

# El SELECT sobre el filtro ya da DESCRIBE implícito sobre la base de datos. Un permiso
# explícito sobre ella daría deriva en cada plan y sobreviviría al destroy
resource "aws_lakeformation_permissions" "analista_filtro" {
  principal   = local.roles_demo.analista.arn
  permissions = ["SELECT"]

  data_cells_filter {
    database_name    = "silver"
    name             = aws_lakeformation_data_cells_filter.analistas_asia.table_data[0].name
    table_catalog_id = local.account_id
    table_name       = "ventas"
  }
}

resource "aws_lakeformation_permissions" "ciencia_bd" {
  principal   = local.roles_demo.ciencia.arn
  permissions = ["DESCRIBE"]

  lf_tag_policy {
    resource_type = "DATABASE"

    expression {
      key    = aws_lakeformation_lf_tag.capa.key
      values = ["silver"]
    }
  }

  depends_on = [aws_lakeformation_resource_lf_tags.silver]
}

resource "aws_lakeformation_permissions" "ciencia_tablas" {
  principal   = local.roles_demo.ciencia.arn
  permissions = ["SELECT", "DESCRIBE"]

  lf_tag_policy {
    resource_type = "TABLE"

    expression {
      key    = aws_lakeformation_lf_tag.capa.key
      values = ["silver"]
    }

    expression {
      key    = aws_lakeformation_lf_tag.sensibilidad.key
      values = ["publico"]
    }
  }

  depends_on = [aws_lakeformation_resource_lf_tags.pii]
}

# --- Opt-in: solo estos dos roles pasan a usar los permisos de Lake Formation ---------------------

resource "aws_lakeformation_opt_in" "demo" {
  for_each = {
    for par in setproduct(keys(local.roles_demo), local.tablas_con_lf) : "${par[0]}-${par[1]}" => {
      rol   = local.roles_demo[par[0]].arn
      tabla = par[1]
    }
  }

  principal {
    data_lake_principal_identifier = each.value.rol
  }

  resource_data {
    table {
      catalog_id    = local.account_id # sin él, cada plan propone reemplazar el opt-in
      database_name = "silver"
      name          = each.value.tabla
    }
  }

  depends_on = [
    aws_lakeformation_resource.silver,
    aws_lakeformation_permissions.analista_filtro,
    aws_lakeformation_permissions.ciencia_tablas,
  ]
}
