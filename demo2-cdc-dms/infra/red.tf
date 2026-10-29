# Red mínima: dos subredes públicas en dos AZ (DMS y RDS lo exigen en sus subnet
# groups). Sin NAT Gateway ni endpoints de interfaz, que cobran por hora.

data "aws_availability_zones" "disponibles" {
  state = "available"
}

resource "aws_vpc" "demo2" {
  cidr_block           = var.cidr_vpc
  enable_dns_support   = true
  enable_dns_hostnames = true # RDS público necesita resolución DNS

  tags = { Name = "curso-aws-hp-demo2" }
}

resource "aws_internet_gateway" "demo2" {
  vpc_id = aws_vpc.demo2.id
  tags   = { Name = "curso-aws-hp-demo2" }
}

resource "aws_subnet" "publica" {
  count                   = 2
  vpc_id                  = aws_vpc.demo2.id
  cidr_block              = cidrsubnet(var.cidr_vpc, 8, count.index)
  availability_zone       = data.aws_availability_zones.disponibles.names[count.index]
  map_public_ip_on_launch = true

  tags = { Name = "curso-aws-hp-demo2-publica-${count.index + 1}" }
}

resource "aws_route_table" "publica" {
  vpc_id = aws_vpc.demo2.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.demo2.id
  }

  tags = { Name = "curso-aws-hp-demo2-publica" }
}

resource "aws_route_table_association" "publica" {
  count          = 2
  subnet_id      = aws_subnet.publica[count.index].id
  route_table_id = aws_route_table.publica.id
}

# Endpoint de gateway para S3: gratuito, el tráfico de DMS a S3 no sale a internet
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.demo2.id
  service_name      = "com.amazonaws.${local.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.publica.id]

  tags = { Name = "curso-aws-hp-demo2-s3" }
}

# --- Security groups -------------------------------------------------------------

data "http" "mi_ip" {
  count = var.mi_ip == "" ? 1 : 0
  url   = "https://checkip.amazonaws.com"
}

locals {
  mi_ip = var.mi_ip != "" ? var.mi_ip : trimspace(data.http.mi_ip[0].response_body)
}

resource "aws_security_group" "dms" {
  name        = "curso-aws-hp-dms"
  description = "Instancia de replicacion de DMS"
  vpc_id      = aws_vpc.demo2.id

  egress {
    description = "Salida a RDS, S3 y Secrets Manager"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "rds" {
  name        = "curso-aws-hp-rds"
  description = "PostgreSQL: solo desde la IP del alumno y desde DMS"
  vpc_id      = aws_vpc.demo2.id

  ingress {
    description = "PostgreSQL desde la IP del alumno"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["${local.mi_ip}/32"]
  }

  ingress {
    description     = "PostgreSQL desde DMS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.dms.id]
  }
}
