terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.70"
    }
  }
  # Estado local (terraform.tfstate en esta carpeta). No se sube a git.
}

provider "aws" {
  region  = var.region
  profile = var.perfil

  default_tags {
    tags = {
      proyecto = "curso-aws-hp"
      sesion   = "1"
      demo     = "base"
    }
  }
}
