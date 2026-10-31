# --- Rol por defecto del namespace: lectura de silver ---------------------------------

data "aws_iam_policy_document" "redshift_confianza" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["redshift.amazonaws.com", "redshift-serverless.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "redshift_silver" {
  statement {
    sid = "CatalogoSilver"
    actions = [
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:GetTable",
      "glue:GetTables",
      "glue:GetPartition",
      "glue:GetPartitions",
    ]
    resources = concat([local.catalogo_arn], local.silver_arns)
  }

  statement {
    sid       = "ListarBucket"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [local.bucket_arn]
  }

  statement {
    sid       = "LeerSilver"
    actions   = ["s3:GetObject"]
    resources = ["${local.bucket_arn}/silver/*"]
  }
}

resource "aws_iam_role" "redshift" {
  name               = "curso-aws-hp-redshift"
  assume_role_policy = data.aws_iam_policy_document.redshift_confianza.json
}

resource "aws_iam_role_policy" "redshift" {
  name   = "lectura-silver"
  role   = aws_iam_role.redshift.id
  policy = data.aws_iam_policy_document.redshift_silver.json
}

# --- Namespace y workgroup -----------------------------------------------------------------

resource "aws_redshiftserverless_namespace" "hp_retail" {
  namespace_name        = "hp-retail"
  db_name               = "dev"
  admin_username        = "admin_retail"
  manage_admin_password = true # Redshift genera la contraseña y la guarda en Secrets Manager
  iam_roles             = [aws_iam_role.redshift.arn]
  default_iam_role_arn  = aws_iam_role.redshift.arn
}

resource "aws_redshiftserverless_workgroup" "hp_retail" {
  namespace_name      = aws_redshiftserverless_namespace.hp_retail.namespace_name
  workgroup_name      = "hp-retail"
  base_capacity       = var.rpu_base
  max_capacity        = 16
  publicly_accessible = true
  subnet_ids          = aws_subnet.publica[*].id
  security_group_ids  = [aws_security_group.redshift.id]

  depends_on = [aws_route_table_association.publica]
}

# Sin consultas no hay cómputo. El límite corta un bucle olvidado: el presupuesto solo avisa
resource "aws_redshiftserverless_usage_limit" "diario" {
  resource_arn  = aws_redshiftserverless_workgroup.hp_retail.arn
  usage_type    = "serverless-compute"
  amount        = 10 # RPU-horas
  period        = "daily"
  breach_action = "deactivate"
}

# --- Usuario de solo lectura de QuickSight ----------------------------------------------------

resource "random_password" "quicksight_ro" {
  length           = 24
  special          = false
  min_upper        = 2
  min_lower        = 2
  min_numeric      = 2
  override_special = ""
}

resource "aws_secretsmanager_secret" "quicksight_ro" {
  name                    = "curso-aws-hp/demo4/quicksight-ro"
  description             = "Usuario de solo lectura de QuickSight en Redshift Serverless"
  recovery_window_in_days = 0 # borrado inmediato en destroy: el nombre se puede reutilizar
}

resource "aws_secretsmanager_secret_version" "quicksight_ro" {
  secret_id = aws_secretsmanager_secret.quicksight_ro.id
  secret_string = jsonencode({
    username = "quicksight_ro"
    password = random_password.quicksight_ro.result
  })
}
