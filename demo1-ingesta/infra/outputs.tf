output "stream_name" {
  value = aws_kinesis_firehose_delivery_stream.ventas.name
}

output "stream_arn" {
  value = aws_kinesis_firehose_delivery_stream.ventas.arn
}

output "bucket_name" {
  value = local.bucket_name
}

output "region" {
  value = local.region
}

output "politica_put_arn" {
  description = "Política para adjuntar al usuario/rol que ejecuta la API (o al task role de ECS)"
  value       = aws_iam_policy.api_put.arn
}
