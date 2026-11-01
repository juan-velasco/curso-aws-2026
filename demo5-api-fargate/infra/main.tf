# Red, roles y log group. El repositorio de ECR, el cluster, la task definition y el service
# se crean en la demo con la CLI, como en las diapositivas (GUION.md), y los borra limpiar_demo5.py.

data "terraform_remote_state" "base" {
  backend = "local"
  config  = { path = "${path.module}/../../infra/base/terraform.tfstate" }
}

data "terraform_remote_state" "demo1" {
  backend = "local"
  config  = { path = "${path.module}/../../demo1-ingesta/infra/terraform.tfstate" }
}

data "aws_caller_identity" "actual" {}

data "aws_availability_zones" "disponibles" {
  state = "available"
}

locals {
  region     = data.terraform_remote_state.base.outputs.region
  account_id = data.aws_caller_identity.actual.account_id
}

# --- Red mínima: 2 subredes públicas e internet gateway, sin NAT ni balanceador ----------

resource "aws_vpc" "api" {
  cidr_block           = var.cidr_vpc
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "curso-aws-hp-api" }
}

resource "aws_internet_gateway" "api" {
  vpc_id = aws_vpc.api.id
  tags   = { Name = "curso-aws-hp-api" }
}

resource "aws_subnet" "publica" {
  count             = 2
  vpc_id            = aws_vpc.api.id
  cidr_block        = cidrsubnet(var.cidr_vpc, 8, count.index)
  availability_zone = data.aws_availability_zones.disponibles.names[count.index]

  tags = { Name = "curso-aws-hp-api-${count.index}" }
}

resource "aws_route_table" "publica" {
  vpc_id = aws_vpc.api.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.api.id
  }

  tags = { Name = "curso-aws-hp-api" }
}

resource "aws_route_table_association" "publica" {
  count          = 2
  subnet_id      = aws_subnet.publica[count.index].id
  route_table_id = aws_route_table.publica.id
}

data "http" "mi_ip" {
  count = var.mi_ip == "" ? 1 : 0
  url   = "https://checkip.amazonaws.com"
}

locals {
  mi_ip = var.mi_ip != "" ? var.mi_ip : trimspace(data.http.mi_ip[0].response_body)
}

resource "aws_security_group" "api" {
  name        = "api-ventas"
  description = "API de ventas: 8000 solo desde la IP del profesor"
  vpc_id      = aws_vpc.api.id

  ingress {
    description = "API desde la IP del profesor"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["${local.mi_ip}/32"]
  }

  egress {
    description = "Salida a ECR, Firehose y CloudWatch Logs"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# --- Roles -------------------------------------------------------------------------------

data "aws_iam_policy_document" "ecs_confianza" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

# Rol propio: ecsTaskExecutionRole puede existir y ser compartido en una cuenta de empresa
resource "aws_iam_role" "ejecucion" {
  name               = "curso-aws-hp-ecs-ejecucion"
  assume_role_policy = data.aws_iam_policy_document.ecs_confianza.json
}

resource "aws_iam_role_policy_attachment" "ejecucion" {
  role       = aws_iam_role.ejecucion.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Las credenciales de la API vienen de aquí. Solo puede escribir en el stream de ventas
resource "aws_iam_role" "tarea" {
  name               = "api-ventas-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_confianza.json
}

resource "aws_iam_role_policy_attachment" "tarea" {
  role       = aws_iam_role.tarea.name
  policy_arn = data.terraform_remote_state.demo1.outputs.politica_put_arn
}

# --- Logs --------------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/api-ventas"
  retention_in_days = 7
}
