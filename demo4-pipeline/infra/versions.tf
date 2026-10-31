terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.70"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.6"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.9"
    }
  }
}

provider "aws" {
  region  = local.region
  profile = var.perfil

  default_tags {
    tags = {
      proyecto = "curso-aws-hp"
      sesion   = "2"
      demo     = "demo4"
    }
  }
}
