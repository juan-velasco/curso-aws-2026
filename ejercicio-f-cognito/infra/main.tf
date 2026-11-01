data "terraform_remote_state" "base" {
  backend = "local"
  config  = { path = "${path.module}/../../infra/base/terraform.tfstate" }
}

locals {
  region = data.terraform_remote_state.base.outputs.region
}

# --- Cognito -----------------------------------------------------------------------------

resource "aws_cognito_user_pool" "tiendas" {
  name                = "tiendas"
  mfa_configuration   = "OFF"
  deletion_protection = "INACTIVE"
}

resource "aws_cognito_user_pool_client" "api" {
  name         = "curso-hola"
  user_pool_id = aws_cognito_user_pool.tiendas.id

  generate_secret = false # cliente público: la CLI no guarda secretos
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH", # solo para laboratorio: la contraseña viaja al servicio
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]
}

resource "aws_cognito_user_group" "tiendas" {
  name         = "tiendas"
  user_pool_id = aws_cognito_user_pool.tiendas.id
}

# --- API REST con integración mock -------------------------------------------------------

resource "aws_api_gateway_rest_api" "hola" {
  name = "curso-hola"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_authorizer" "cognito" {
  name            = "cognito-tiendas"
  rest_api_id     = aws_api_gateway_rest_api.hola.id
  type            = "COGNITO_USER_POOLS"
  provider_arns   = [aws_cognito_user_pool.tiendas.arn]
  identity_source = "method.request.header.Authorization"
}

resource "aws_api_gateway_resource" "hola" {
  rest_api_id = aws_api_gateway_rest_api.hola.id
  parent_id   = aws_api_gateway_rest_api.hola.root_resource_id
  path_part   = "hola"
}

resource "aws_api_gateway_method" "hola" {
  rest_api_id   = aws_api_gateway_rest_api.hola.id
  resource_id   = aws_api_gateway_resource.hola.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "hola" {
  rest_api_id = aws_api_gateway_rest_api.hola.id
  resource_id = aws_api_gateway_resource.hola.id
  http_method = aws_api_gateway_method.hola.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "hola" {
  rest_api_id = aws_api_gateway_rest_api.hola.id
  resource_id = aws_api_gateway_resource.hola.id
  http_method = aws_api_gateway_method.hola.http_method
  status_code = "200"
}

resource "aws_api_gateway_integration_response" "hola" {
  rest_api_id = aws_api_gateway_rest_api.hola.id
  resource_id = aws_api_gateway_resource.hola.id
  http_method = aws_api_gateway_method.hola.http_method
  status_code = aws_api_gateway_method_response.hola.status_code

  response_templates = {
    "application/json" = <<-VTL
      {
        "mensaje": "Hola desde la API protegida",
        "usuario": "$context.authorizer.claims['cognito:username']",
        "grupos": "$context.authorizer.claims['cognito:groups']"
      }
    VTL
  }

  depends_on = [aws_api_gateway_integration.hola]
}

resource "aws_api_gateway_deployment" "hola" {
  rest_api_id = aws_api_gateway_rest_api.hola.id

  # Una API REST no publica sus cambios hasta que se despliega de nuevo
  triggers = {
    cambios = sha1(jsonencode([
      aws_api_gateway_resource.hola.id,
      aws_api_gateway_method.hola.id,
      aws_api_gateway_method.hola.authorizer_id,
      aws_api_gateway_integration.hola.request_templates,
      aws_api_gateway_integration_response.hola.response_templates,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "prod" {
  rest_api_id   = aws_api_gateway_rest_api.hola.id
  deployment_id = aws_api_gateway_deployment.hola.id
  stage_name    = "prod"
}
