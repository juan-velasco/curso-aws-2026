data "terraform_remote_state" "base" {
  backend = "local"
  config  = { path = "${path.module}/../../infra/base/terraform.tfstate" }
}

data "aws_availability_zones" "disponibles" {
  state = "available"
}

locals {
  region     = data.terraform_remote_state.base.outputs.region
  bucket_arn = data.terraform_remote_state.base.outputs.bucket_arn
}

# --- Red: el dominio necesita VPC aunque salga a internet por la de SageMaker ------------

resource "aws_vpc" "studio" {
  cidr_block           = var.cidr_vpc
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "curso-aws-hp-studio" }
}

resource "aws_internet_gateway" "studio" {
  vpc_id = aws_vpc.studio.id
  tags   = { Name = "curso-aws-hp-studio" }
}

resource "aws_subnet" "publica" {
  count             = 2
  vpc_id            = aws_vpc.studio.id
  cidr_block        = cidrsubnet(var.cidr_vpc, 8, count.index)
  availability_zone = data.aws_availability_zones.disponibles.names[count.index]

  tags = { Name = "curso-aws-hp-studio-${count.index}" }
}

resource "aws_route_table" "publica" {
  vpc_id = aws_vpc.studio.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.studio.id
  }

  tags = { Name = "curso-aws-hp-studio" }
}

resource "aws_route_table_association" "publica" {
  count          = 2
  subnet_id      = aws_subnet.publica[count.index].id
  route_table_id = aws_route_table.publica.id
}

# --- Rol de ejecución de Studio ----------------------------------------------------------

data "aws_iam_policy_document" "sagemaker_confianza" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sagemaker" {
  name               = "curso-aws-hp-sagemaker"
  assume_role_policy = data.aws_iam_policy_document.sagemaker_confianza.json
}

resource "aws_iam_role_policy_attachment" "sagemaker" {
  role       = aws_iam_role.sagemaker.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

# Del bucket del lago, solo ml/
data "aws_iam_policy_document" "sagemaker_ml" {
  statement {
    sid       = "ListarMl"
    actions   = ["s3:ListBucket"]
    resources = [local.bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["ml/*"]
    }
  }

  statement {
    sid = "LeerEscribirMl"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
    ]
    resources = ["${local.bucket_arn}/ml/*"]
  }
}

resource "aws_iam_role_policy" "sagemaker_ml" {
  name   = "lectura-escritura-ml"
  role   = aws_iam_role.sagemaker.id
  policy = data.aws_iam_policy_document.sagemaker_ml.json
}

# --- Dominio y perfil --------------------------------------------------------------------

resource "aws_sagemaker_domain" "curso" {
  domain_name             = "curso-aws-hp"
  auth_mode               = "IAM"
  app_network_access_type = "PublicInternetOnly"
  vpc_id                  = aws_vpc.studio.id
  subnet_ids              = aws_subnet.publica[*].id

  # Sin esto, destroy deja el volumen EFS del dominio
  retention_policy {
    home_efs_file_system = "Delete"
  }

  default_user_settings {
    execution_role = aws_iam_role.sagemaker.arn
  }

  default_space_settings {
    execution_role = aws_iam_role.sagemaker.arn

    jupyter_lab_app_settings {
      default_resource_spec {
        instance_type = var.instancia_jupyterlab
      }

      app_lifecycle_management {
        idle_settings {
          lifecycle_management        = "ENABLED"
          idle_timeout_in_minutes     = var.minutos_inactividad
          min_idle_timeout_in_minutes = var.minutos_inactividad
          max_idle_timeout_in_minutes = 480 # quien usa el space puede alargarlo hasta aquí
        }
      }
    }
  }

  depends_on = [aws_route_table_association.publica]

  # SageMaker devuelve un bloque vacío que no se puede declarar: sin esto, el plan nunca queda limpio
  lifecycle {
    ignore_changes = [default_user_settings[0].studio_web_portal_settings]
  }
}

resource "aws_sagemaker_user_profile" "profesor" {
  domain_id         = aws_sagemaker_domain.curso.id
  user_profile_name = "profesor"
}
