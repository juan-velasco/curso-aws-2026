data "terraform_remote_state" "base" {
  backend = "local"

  config = {
    path = "${path.module}/../../infra/base/terraform.tfstate"
  }
}

locals {
  region      = data.terraform_remote_state.base.outputs.region
  bucket_name = data.terraform_remote_state.base.outputs.bucket_name
  bucket_arn  = data.terraform_remote_state.base.outputs.bucket_arn
  db_name     = "retail"
}

resource "aws_db_subnet_group" "demo2" {
  name       = "curso-aws-hp-demo2"
  subnet_ids = aws_subnet.publica[*].id
}

resource "aws_db_parameter_group" "cdc" {
  name   = "curso-aws-hp-pg${var.version_postgres}-cdc"
  family = "postgres${var.version_postgres}"

  # wal_level = logical (estático: se aplica al crear la instancia)
  parameter {
    name         = "rds.logical_replication"
    value        = "1"
    apply_method = "pending-reboot"
  }

  # Recomendado por DMS: sin timeout de las conexiones de replicación
  parameter {
    name  = "wal_sender_timeout"
    value = "0"
  }
}

# Contraseña maestra: queda en el estado local de Terraform (no subirlo a git)
resource "random_password" "maestra" {
  length  = 24
  special = false
}

resource "aws_db_instance" "retail" {
  identifier     = "curso-aws-hp-retail"
  engine         = "postgres"
  engine_version = var.version_postgres
  instance_class = "db.t4g.micro"

  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = local.db_name
  username = "retail_admin"
  password = random_password.maestra.result

  db_subnet_group_name   = aws_db_subnet_group.demo2.name
  parameter_group_name   = aws_db_parameter_group.cdc.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = true # semilla desde el portátil sin bastión
  multi_az               = false

  backup_retention_period = 0 # sin copias: entorno efímero
  skip_final_snapshot     = true
  deletion_protection     = false
  apply_immediately       = true
}
