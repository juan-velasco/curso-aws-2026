data "terraform_remote_state" "base" {
  backend = "local"
  config  = { path = "${path.module}/../../infra/base/terraform.tfstate" }
}

data "aws_caller_identity" "actual" {}

locals {
  region = data.terraform_remote_state.base.outputs.region
}

# --- Servicios: solo lo que no estuviera activo ------------------------------------------

resource "aws_guardduty_detector" "curso" {
  count  = var.crear_detector_guardduty ? 1 : 0
  enable = true
}

resource "aws_inspector2_enabler" "ecr" {
  count          = var.activar_inspector_ecr ? 1 : 0
  account_ids    = [data.aws_caller_identity.actual.account_id]
  resource_types = ["ECR"]
}

# --- Hallazgos graves a un email ---------------------------------------------------------

resource "aws_sns_topic" "seguridad" {
  name = "curso-aws-hp-seguridad"
}

data "aws_iam_policy_document" "seguridad" {
  statement {
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.seguridad.arn]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.hallazgos_graves.arn]
    }
  }
}

resource "aws_sns_topic_policy" "seguridad" {
  arn    = aws_sns_topic.seguridad.arn
  policy = data.aws_iam_policy_document.seguridad.json
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.seguridad.arn
  protocol  = "email"
  endpoint  = var.email_alertas
}

resource "aws_cloudwatch_event_rule" "hallazgos_graves" {
  name        = "curso-guardduty-graves"
  description = "Hallazgos de GuardDuty con severidad 7 o más"

  event_pattern = jsonencode({
    source        = ["aws.guardduty"]
    "detail-type" = ["GuardDuty Finding"]
    detail = {
      severity = [{ numeric = [">=", 7] }]
    }
  })
}

resource "aws_cloudwatch_event_target" "sns" {
  rule = aws_cloudwatch_event_rule.hallazgos_graves.name
  arn  = aws_sns_topic.seguridad.arn
}

# --- Repositorio de la imagen antigua ----------------------------------------------------

resource "aws_ecr_repository" "antigua" {
  name         = "curso-imagen-antigua"
  force_delete = true
}
