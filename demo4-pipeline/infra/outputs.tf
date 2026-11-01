output "bucket_name" {
  value = local.bucket_name
}

output "region" {
  value = local.region
}

output "jobs_glue" {
  value = { for k, job in aws_glue_job.bronze_a_silver : k => job.name }
}

output "redshift_workgroup" {
  value = aws_redshiftserverless_workgroup.hp_retail.workgroup_name
}

output "redshift_endpoint" {
  value = aws_redshiftserverless_workgroup.hp_retail.endpoint[0].address
}

output "secreto_admin_arn" {
  value = aws_redshiftserverless_namespace.hp_retail.admin_password_secret_arn
}

output "secreto_quicksight_ro" {
  value = aws_secretsmanager_secret.quicksight_ro.name
}

output "rol_pipeline" {
  value = aws_iam_role.pipeline.name
}

output "maquina_arn" {
  value = aws_sfn_state_machine.pipeline.arn
}

output "tema_sns" {
  value = aws_sns_topic.pipeline.arn
}

output "quicksight_dataset_id" {
  value = var.quicksight_activo ? aws_quicksight_data_set.ventas[0].data_set_id : null
}

output "quicksight_dataset_arn" {
  value = var.quicksight_activo ? aws_quicksight_data_set.ventas[0].arn : null
}

output "quicksight_fuente_arn" {
  description = "Fuente de datos de QuickSight, que reutiliza la demo 6"
  value       = var.quicksight_activo ? aws_quicksight_data_source.gold[0].arn : ""
}
