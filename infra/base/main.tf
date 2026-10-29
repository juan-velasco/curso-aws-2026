data "aws_caller_identity" "actual" {}

locals {
  sufijo      = var.sufijo_bucket != "" ? var.sufijo_bucket : data.aws_caller_identity.actual.account_id
  bucket_name = "retail-company-datalake-prod-${local.sufijo}"
}

# --- Bucket del lago (bronze, silver, gold) -----------------------------------

resource "aws_s3_bucket" "lago" {
  bucket = local.bucket_name

  # Entorno de curso: `terraform destroy` borra el bucket aunque tenga objetos
  # (y todas sus versiones). En producción, false.
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "lago" {
  bucket = aws_s3_bucket.lago.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lago" {
  bucket = aws_s3_bucket.lago.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256" # SSE-S3
    }
  }
}

resource "aws_s3_bucket_versioning" "lago" {
  bucket = aws_s3_bucket.lago.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "lago" {
  bucket = aws_s3_bucket.lago.id

  # El versionado debe estar activo antes de las reglas sobre versiones no actuales
  depends_on = [aws_s3_bucket_versioning.lago]

  rule {
    id     = "bronze-por-niveles"
    status = "Enabled"

    filter {
      prefix = "bronze/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }

    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }
  }

  rule {
    id     = "versiones-no-actuales"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "athena-results"
    status = "Enabled"

    filter {
      prefix = "athena-results/"
    }

    expiration {
      days = 7
    }
  }
}

# --- Presupuesto mensual con avisos por email ---------------------------------

resource "aws_budgets_budget" "mensual" {
  name         = "curso-aws-hp-mensual"
  budget_type  = "COST"
  limit_amount = format("%.1f", var.presupuesto_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = [80, 100]

    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.email_alertas]
    }
  }
}
