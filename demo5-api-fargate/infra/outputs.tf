output "subredes" {
  value = aws_subnet.publica[*].id
}

output "security_group" {
  value = aws_security_group.api.id
}

output "execution_role_arn" {
  value = aws_iam_role.ejecucion.arn
}

output "task_role_arn" {
  value = aws_iam_role.tarea.arn
}

output "log_group" {
  value = aws_cloudwatch_log_group.api.name
}

output "region" {
  value = local.region
}

output "account_id" {
  value = local.account_id
}

output "stream_name" {
  value = data.terraform_remote_state.demo1.outputs.stream_name
}

output "bucket_name" {
  value = data.terraform_remote_state.base.outputs.bucket_name
}
