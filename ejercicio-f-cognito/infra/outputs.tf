output "region" {
  value = local.region
}

output "user_pool_id" {
  value = aws_cognito_user_pool.tiendas.id
}

output "client_id" {
  value = aws_cognito_user_pool_client.api.id
}

output "url_api" {
  value = "${aws_api_gateway_stage.prod.invoke_url}/hola"
}
