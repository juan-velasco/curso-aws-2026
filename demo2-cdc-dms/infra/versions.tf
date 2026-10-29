terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.70"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.9"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.6"
    }
  }
  # Estado local. ATENCIÓN: contiene la contraseña maestra de RDS en claro.
  # No se sube a git (.gitignore) y se borra con `terraform destroy`.
}

provider "aws" {
  region  = local.region
  profile = var.perfil

  default_tags {
    tags = {
      proyecto = "curso-aws-hp"
      sesion   = "1"
      demo     = "demo2"
    }
  }
}
