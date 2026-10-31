locals {
  clave_control = "control/calidad/ventas/ultima.json"

  # Sin QuickSight, el estado RefrescarSPICE no hace nada
  refrescar_spice = var.quicksight_activo ? jsonencode({
    Type     = "Task"
    Resource = "arn:aws:states:::aws-sdk:quicksight:createIngestion"
    Parameters = {
      AwsAccountId    = local.account_id
      DataSetId       = local.id_dataset
      "IngestionId.$" = "States.UUID()"
    }
    ResultPath = null
    Catch = [{
      ErrorEquals = ["States.ALL"]
      ResultPath  = "$.error"
      Next        = "NotificarFallo"
    }]
    Next = "NotificarOK"
    }) : jsonencode({
    Type = "Pass"
    Next = "NotificarOK"
  })
}

# --- Avisos -----------------------------------------------------------------------------

resource "aws_sns_topic" "pipeline" {
  name = "curso-aws-hp-pipeline"
}

resource "aws_sns_topic_subscription" "pipeline" {
  topic_arn = aws_sns_topic.pipeline.arn
  protocol  = "email"
  endpoint  = var.email_alertas
}

# --- Rol de la máquina ---------------------------------------------------------------------

data "aws_iam_policy_document" "states_confianza" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "pipeline" {
  statement {
    sid       = "Jobs"
    actions   = ["glue:StartJobRun", "glue:GetJobRun", "glue:GetJobRuns", "glue:BatchStopJobRun"]
    resources = [for job in aws_glue_job.bronze_a_silver : job.arn]
  }

  statement {
    sid       = "Control"
    actions   = ["s3:GetObject"]
    resources = ["${local.bucket_arn}/${local.clave_control}"]
  }

  statement {
    sid       = "EjecutarEnRedshift"
    actions   = ["redshift-data:ExecuteStatement"]
    resources = [aws_redshiftserverless_workgroup.hp_retail.arn]
  }

  statement {
    sid       = "SeguirSentencia"
    actions   = ["redshift-data:DescribeStatement"]
    resources = ["*"] # esta acción no admite restricción por recurso
  }

  statement {
    sid       = "CredencialesRedshift"
    actions   = ["redshift-serverless:GetCredentials"]
    resources = [aws_redshiftserverless_workgroup.hp_retail.arn]
  }

  statement {
    sid       = "Avisos"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.pipeline.arn]
  }

  dynamic "statement" {
    for_each = var.quicksight_activo ? [1] : []
    content {
      sid       = "RefrescarSPICE"
      actions   = ["quicksight:CreateIngestion"]
      resources = ["arn:aws:quicksight:${local.region}:${local.account_id}:dataset/${local.id_dataset}/*"]
    }
  }

  # startJobRun.sync sigue el job con una regla de EventBridge gestionada por Step Functions
  statement {
    sid       = "ReglaSync"
    actions   = ["events:PutTargets", "events:PutRule", "events:DescribeRule"]
    resources = ["arn:aws:events:${local.region}:${local.account_id}:rule/StepFunctionsGetEventsForGlueJobRunsRule"]
  }
}

resource "aws_iam_role" "pipeline" {
  name               = "curso-aws-hp-pipeline"
  assume_role_policy = data.aws_iam_policy_document.states_confianza.json
}

resource "aws_iam_role_policy" "pipeline" {
  name   = "pipeline-bronze-a-gold"
  role   = aws_iam_role.pipeline.id
  policy = data.aws_iam_policy_document.pipeline.json
}

# --- Máquina de estados -----------------------------------------------------------------------

resource "aws_sfn_state_machine" "pipeline" {
  name     = "curso-aws-hp-pipeline"
  type     = "STANDARD"
  role_arn = aws_iam_role.pipeline.arn

  definition = templatefile("${path.module}/../stepfunctions/pipeline.asl.json", {
    job_ventas      = aws_glue_job.bronze_a_silver["ventas"].name
    job_maestros    = aws_glue_job.bronze_a_silver["maestros"].name
    bucket          = local.bucket_name
    clave_control   = local.clave_control
    workgroup       = aws_redshiftserverless_workgroup.hp_retail.workgroup_name
    tema_sns        = aws_sns_topic.pipeline.arn
    refrescar_spice = local.refrescar_spice
  })
}

# --- Programación horaria: creada, pero desactivada salvo con programacion_activa = true ----------

data "aws_iam_policy_document" "scheduler_confianza" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    actions   = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.pipeline.arn]
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "curso-aws-hp-pipeline-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_confianza.json
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "lanzar-pipeline"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}

resource "aws_scheduler_schedule" "pipeline" {
  name                         = "curso-aws-hp-pipeline-horario"
  schedule_expression          = "cron(0 * * * ? *)"
  schedule_expression_timezone = "Europe/Madrid"
  state                        = var.programacion_activa ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_sfn_state_machine.pipeline.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({ forzar_fallo = "false" })
  }
}
