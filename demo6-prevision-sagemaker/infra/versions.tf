terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.70"
    }
  }
}

provider "aws" {
  region  = local.region
  profile = var.perfil

  default_tags {
    tags = {
      proyecto = "curso-aws-hp"
      sesion   = "3"
      demo     = "demo6"
    }
  }
}
