# Red mínima de Redshift Serverless: subredes públicas e internet gateway, sin NAT.
# Sin Enhanced VPC Routing bastan 2 subredes en 2 AZ; con 3 hay margen si una AZ no admite el servicio.

data "aws_availability_zones" "disponibles" {
  state = "available"
}

resource "aws_vpc" "redshift" {
  cidr_block           = var.cidr_vpc
  enable_dns_support   = true
  enable_dns_hostnames = true # el endpoint público se resuelve por DNS

  tags = { Name = "curso-aws-hp-redshift" }
}

resource "aws_internet_gateway" "redshift" {
  vpc_id = aws_vpc.redshift.id
  tags   = { Name = "curso-aws-hp-redshift" }
}

resource "aws_subnet" "publica" {
  count             = 3
  vpc_id            = aws_vpc.redshift.id
  cidr_block        = cidrsubnet(var.cidr_vpc, 8, count.index)
  availability_zone = data.aws_availability_zones.disponibles.names[count.index]

  tags = { Name = "curso-aws-hp-redshift-${count.index}" }
}

resource "aws_route_table" "publica" {
  vpc_id = aws_vpc.redshift.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.redshift.id
  }

  tags = { Name = "curso-aws-hp-redshift" }
}

resource "aws_route_table_association" "publica" {
  count          = 3
  subnet_id      = aws_subnet.publica[count.index].id
  route_table_id = aws_route_table.publica.id
}

# --- Security group ------------------------------------------------------------------

data "http" "mi_ip" {
  count = var.mi_ip == "" ? 1 : 0
  url   = "https://checkip.amazonaws.com"
}

locals {
  mi_ip = var.mi_ip != "" ? var.mi_ip : trimspace(data.http.mi_ip[0].response_body)
}

resource "aws_security_group" "redshift" {
  name        = "curso-aws-hp-redshift"
  description = "Redshift Serverless: 5439 solo desde QuickSight y la IP del profesor"
  vpc_id      = aws_vpc.redshift.id

  ingress {
    description = "Redshift desde QuickSight en la region"
    from_port   = 5439
    to_port     = 5439
    protocol    = "tcp"
    cidr_blocks = [var.cidr_quicksight]
  }

  ingress {
    description = "Redshift desde la IP del profesor"
    from_port   = 5439
    to_port     = 5439
    protocol    = "tcp"
    cidr_blocks = ["${local.mi_ip}/32"]
  }

  egress {
    description = "Salida a S3 y al Glue Data Catalog"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
