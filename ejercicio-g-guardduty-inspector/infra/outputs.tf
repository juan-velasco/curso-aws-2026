output "region" {
  value = local.region
}

output "account_id" {
  value = data.aws_caller_identity.actual.account_id
}

output "tema_sns" {
  value = aws_sns_topic.seguridad.arn
}

output "repositorio_antigua" {
  value = aws_ecr_repository.antigua.repository_url
}
