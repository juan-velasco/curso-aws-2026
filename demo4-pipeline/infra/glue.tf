data "terraform_remote_state" "base" {
  backend = "local"
  config  = { path = "${path.module}/../../infra/base/terraform.tfstate" }
}

data "aws_caller_identity" "actual" {}

locals {
  region      = data.terraform_remote_state.base.outputs.region
  bucket_name = data.terraform_remote_state.base.outputs.bucket_name
  bucket_arn  = data.terraform_remote_state.base.outputs.bucket_arn
  account_id  = data.aws_caller_identity.actual.account_id

  catalogo_arn = "arn:aws:glue:${local.region}:${local.account_id}:catalog"
  silver_arns = [
    "arn:aws:glue:${local.region}:${local.account_id}:database/silver",
    "arn:aws:glue:${local.region}:${local.account_id}:table/silver/*",
  ]

  dir_glue = "${path.module}/../glue"
  scripts_glue = {
    ventas           = "bronze_a_silver_ventas.py"
    maestros         = "bronze_a_silver_maestros.py"
    transformaciones = "transformaciones.py"
  }

  # Configuración del catálogo Iceberg (diapositiva «Anatomía de un Glue Job»). Glue admite
  # un solo argumento --conf: las demás propiedades van encadenadas en su valor
  conf_iceberg = join(" --conf ", [
    "spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
    "spark.sql.catalog.glue_catalog=org.apache.iceberg.spark.SparkCatalog",
    "spark.sql.catalog.glue_catalog.warehouse=s3://${local.bucket_name}/silver/",
    "spark.sql.catalog.glue_catalog.catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog",
    "spark.sql.catalog.glue_catalog.io-impl=org.apache.iceberg.aws.s3.S3FileIO",
  ])
}

# --- Scripts de los jobs -------------------------------------------------------------------

resource "aws_s3_object" "script_glue" {
  for_each = local.scripts_glue

  bucket = local.bucket_name
  key    = "artefactos/glue/${each.value}"
  source = "${local.dir_glue}/${each.value}"
  etag   = filemd5("${local.dir_glue}/${each.value}")
}

# --- Rol de los jobs --------------------------------------------------------------------------

data "aws_iam_policy_document" "glue_confianza" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "glue_jobs" {
  statement {
    sid       = "ListarBucket"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [local.bucket_arn]
  }

  statement {
    sid     = "LeerBronzeYArtefactos"
    actions = ["s3:GetObject"]
    resources = [
      "${local.bucket_arn}/bronze/ventas/*",
      "${local.bucket_arn}/bronze/cdc/*",
      "${local.bucket_arn}/artefactos/*",
    ]
  }

  statement {
    sid     = "EscribirSilverYControl"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = [
      "${local.bucket_arn}/silver/*",
      "${local.bucket_arn}/control/*",
    ]
  }

  statement {
    sid = "CatalogoSilver"
    actions = [
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:GetTable",
      "glue:GetTables",
      "glue:UpdateTable",
    ]
    resources = concat([local.catalogo_arn], local.silver_arns)
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws-glue/*"]
  }

  statement {
    sid       = "Metricas"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"] # esta acción no admite restricción por recurso

    condition {
      test     = "StringLike"
      variable = "cloudwatch:namespace"
      values   = ["Glue", "Glue Data Quality"]
    }
  }

  statement {
    sid       = "DataQuality"
    actions   = ["glue:PublishDataQuality"]
    resources = ["arn:aws:glue:${local.region}:${local.account_id}:dataQualityRuleset/*"]
  }
}

resource "aws_iam_role" "glue_jobs" {
  name               = "curso-aws-hp-glue-jobs"
  assume_role_policy = data.aws_iam_policy_document.glue_confianza.json
}

resource "aws_iam_role_policy" "glue_jobs" {
  name   = "bronze-a-silver"
  role   = aws_iam_role.glue_jobs.id
  policy = data.aws_iam_policy_document.glue_jobs.json
}

# --- Jobs -----------------------------------------------------------------------------------------

resource "aws_glue_job" "bronze_a_silver" {
  for_each = {
    ventas   = "bronze-a-silver-ventas"
    maestros = "bronze-a-silver-maestros"
  }

  name              = each.value
  role_arn          = aws_iam_role.glue_jobs.arn
  glue_version      = "5.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 30
  execution_class   = var.clase_ejecucion_glue
  max_retries       = 0 # los reintentos los hace la máquina de estados

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${local.bucket_name}/${aws_s3_object.script_glue[each.key].key}"
  }

  execution_property {
    max_concurrent_runs = 1
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--datalake-formats"                 = "iceberg"
    "--conf"                             = local.conf_iceberg
    "--job-bookmark-option"              = "job-bookmark-enable"
    "--extra-py-files"                   = "s3://${local.bucket_name}/${aws_s3_object.script_glue["transformaciones"].key}"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--BUCKET"                           = local.bucket_name
    "--FORZAR_FALLO"                     = "false"
  }
}
