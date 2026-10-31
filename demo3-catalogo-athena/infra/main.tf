data "terraform_remote_state" "base" {
  backend = "local"
  config  = { path = "${path.module}/../../infra/base/terraform.tfstate" }
}

locals {
  region      = data.terraform_remote_state.base.outputs.region
  bucket_name = data.terraform_remote_state.base.outputs.bucket_name
  bucket_arn  = data.terraform_remote_state.base.outputs.bucket_arn
}

# --- Bases de datos del Glue Data Catalog --------------------------------------------
# silver la usa la demo 4. bronze.ventas no se crea aquí: se crea en la demo desde Athena.

resource "aws_glue_catalog_database" "bronze" {
  name        = "bronze"
  description = "Capa bronze del lago: ventas (partition projection) y maestros de CDC (crawler)"
}

resource "aws_glue_catalog_database" "silver" {
  name         = "silver"
  description  = "Capa silver del lago: tablas Iceberg"
  location_uri = "s3://${local.bucket_name}/silver/"
}

# --- Crawler de los maestros de CDC ------------------------------------------------------

data "aws_iam_policy_document" "glue_confianza" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "crawler" {
  name               = "curso-bronze-cdc-crawler"
  assume_role_policy = data.aws_iam_policy_document.glue_confianza.json
}

# Catálogo y logs; el acceso a S3 de esta política solo cubre buckets aws-glue-*
resource "aws_iam_role_policy_attachment" "crawler_glue" {
  role       = aws_iam_role.crawler.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

data "aws_iam_policy_document" "crawler_s3" {
  statement {
    sid       = "Listar"
    actions   = ["s3:ListBucket"]
    resources = [local.bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["bronze/cdc/*"]
    }
  }

  statement {
    sid       = "Leer"
    actions   = ["s3:GetObject"]
    resources = ["${local.bucket_arn}/bronze/cdc/*"]
  }
}

resource "aws_iam_role_policy" "crawler_s3" {
  name   = "lectura-bronze-cdc"
  role   = aws_iam_role.crawler.id
  policy = data.aws_iam_policy_document.crawler_s3.json
}

resource "aws_glue_crawler" "bronze_cdc" {
  name          = "curso-bronze-cdc"
  description   = "Maestros de CDC: bronze.productos. Se lanza en la demo"
  database_name = aws_glue_catalog_database.bronze.name
  role          = aws_iam_role.crawler.arn

  # Solo productos. clientes no se rastrea: la carga completa (raíz, sin Op) y los cambios
  # (AAAA/MM/DD/, con Op) no le encajan al crawler. Se crea con sql/04_bronze_clientes.sql
  s3_target {
    path       = "s3://${local.bucket_name}/bronze/cdc/public/productos/"
    exclusions = ["**/_SUCCESS", "**/*.tmp", "**/_temporary/**"]
  }

  # Registrar los cambios de esquema y no borrar nada
  schema_change_policy {
    update_behavior = "LOG"
    delete_behavior = "LOG"
  }

  # Nivel 5 = bucket (1) / bronze (2) / cdc (3) / public (4) / productos (5)
  configuration = jsonencode({
    Version = 1.0
    Grouping = {
      TableGroupingPolicy     = "CombineCompatibleSchemas"
      TableLevelConfiguration = 5
    }
  })

  depends_on = [aws_iam_role_policy_attachment.crawler_glue, aws_iam_role_policy.crawler_s3]
}

# --- Workgroup de Athena ---------------------------------------------------------------

resource "aws_athena_workgroup" "curso" {
  name          = "curso"
  description   = "Consultas del curso, con límite de 10 GB escaneados por consulta"
  force_destroy = true

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = 10737418240 # 10 GB

    result_configuration {
      output_location = "s3://${local.bucket_name}/athena-results/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}
