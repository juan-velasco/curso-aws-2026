# El bucket y la región se leen del estado local del módulo base
data "terraform_remote_state" "base" {
  backend = "local"

  config = {
    path = "${path.module}/../../infra/base/terraform.tfstate"
  }
}

data "aws_caller_identity" "actual" {}

locals {
  region      = data.terraform_remote_state.base.outputs.region
  bucket_name = data.terraform_remote_state.base.outputs.bucket_name
  bucket_arn  = data.terraform_remote_state.base.outputs.bucket_arn
  account_id  = data.aws_caller_identity.actual.account_id

  prefijo_bronze  = "bronze/ventas/"
  prefijo_errores = "errors/ventas/"
}

# --- Logs de errores de entrega -------------------------------------------------

resource "aws_cloudwatch_log_group" "firehose" {
  name              = "/aws/kinesisfirehose/${var.stream_name}"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_stream" "entrega_s3" {
  name           = "DestinationDelivery"
  log_group_name = aws_cloudwatch_log_group.firehose.name
}

# --- Rol de Firehose: escribir en bronze/ventas y errors/ventas ------------------

data "aws_iam_policy_document" "firehose_confianza" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["firehose.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [local.account_id]
    }
  }
}

data "aws_iam_policy_document" "firehose_permisos" {
  statement {
    sid       = "Bucket"
    actions   = ["s3:GetBucketLocation", "s3:ListBucket", "s3:ListBucketMultipartUploads"]
    resources = [local.bucket_arn]
  }

  statement {
    sid = "Objetos"
    actions = [
      "s3:AbortMultipartUpload",
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = [
      "${local.bucket_arn}/${local.prefijo_bronze}*",
      "${local.bucket_arn}/${local.prefijo_errores}*",
    ]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.firehose.arn}:log-stream:*"]
  }
}

resource "aws_iam_role" "firehose" {
  name               = "firehose-${var.stream_name}"
  assume_role_policy = data.aws_iam_policy_document.firehose_confianza.json
}

resource "aws_iam_role_policy" "firehose" {
  name   = "escritura-bronze-ventas"
  role   = aws_iam_role.firehose.id
  policy = data.aws_iam_policy_document.firehose_permisos.json
}

# --- Stream de Firehose: Direct PUT -> S3 bronze ----------------------------------

resource "aws_kinesis_firehose_delivery_stream" "ventas" {
  name        = var.stream_name
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn   = aws_iam_role.firehose.arn
    bucket_arn = local.bucket_arn

    # Fecha de LLEGADA a Firehose, no la fecha de negocio (event_ts)
    prefix              = "${local.prefijo_bronze}anio=!{timestamp:yyyy}/mes=!{timestamp:MM}/dia=!{timestamp:dd}/"
    error_output_prefix = "${local.prefijo_errores}!{firehose:error-output-type}/!{timestamp:yyyy/MM/dd}/"
    custom_time_zone    = "UTC" # zona horaria de !{timestamp}

    buffering_interval = 30 # segundos
    buffering_size     = 5  # MiB
    compression_format = "GZIP"

    # Athena decide la descompresión por la extensión: sin .gz no lee los ficheros
    file_extension = ".json.gz"

    # Sin Lambda, sin conversión de formato y sin particionado dinámico:
    # bronze es una copia fiel de lo que acepta la API.

    cloudwatch_logging_options {
      enabled         = true
      log_group_name  = aws_cloudwatch_log_group.firehose.name
      log_stream_name = aws_cloudwatch_log_stream.entrega_s3.name
    }
  }

  depends_on = [aws_iam_role_policy.firehose]
}

# --- Política para quien envía a Firehose (la API) ----------------------------------
# Sesión 1: se puede adjuntar al usuario o rol del alumno. Sesión 3: task role de ECS.

data "aws_iam_policy_document" "put" {
  statement {
    actions   = ["firehose:PutRecord", "firehose:PutRecordBatch"]
    resources = [aws_kinesis_firehose_delivery_stream.ventas.arn]
  }
}

resource "aws_iam_policy" "api_put" {
  name        = "api-ventas-firehose-put"
  description = "Permite a la API de ventas enviar registros al stream ${var.stream_name}"
  policy      = data.aws_iam_policy_document.put.json
}

# --- Alarma de frescura de los datos ------------------------------------------------

resource "aws_sns_topic" "alertas" {
  count = var.email_alertas != "" ? 1 : 0
  name  = "${var.stream_name}-alertas"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.email_alertas != "" ? 1 : 0
  topic_arn = aws_sns_topic.alertas[0].arn
  protocol  = "email"
  endpoint  = var.email_alertas # hay que confirmar la suscripción desde el email
}

resource "aws_cloudwatch_metric_alarm" "data_freshness" {
  alarm_name        = "${var.stream_name}-data-freshness"
  alarm_description = "Los registros más antiguos de Firehose llevan más de 2 minutos sin llegar a S3"
  namespace         = "AWS/Firehose"
  metric_name       = "DeliveryToS3.DataFreshness"
  dimensions = {
    DeliveryStreamName = aws_kinesis_firehose_delivery_stream.ventas.name
  }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 120
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching" # sin generador no hay métricas
  alarm_actions       = aws_sns_topic.alertas[*].arn
  ok_actions          = aws_sns_topic.alertas[*].arn
}
