output "rds_endpoint" {
  value = aws_db_instance.retail.address
}

output "rds_port" {
  value = aws_db_instance.retail.port
}

output "db_name" {
  value = local.db_name
}

output "usuario_maestro" {
  value = aws_db_instance.retail.username
}

output "password_maestra" {
  description = "terraform output -raw password_maestra"
  value       = random_password.maestra.result
  sensitive   = true
}

output "secreto_nombre" {
  value = aws_secretsmanager_secret.dms_user.name
}

output "tarea_arn" {
  value = aws_dms_replication_task.clientes_productos.replication_task_arn
}

output "instancia_replicacion_arn" {
  value = aws_dms_replication_instance.demo2.replication_instance_arn
}

output "endpoint_origen_arn" {
  value = aws_dms_endpoint.origen.endpoint_arn
}

output "endpoint_destino_arn" {
  value = aws_dms_s3_endpoint.bronze.endpoint_arn
}

output "bucket_name" {
  value = local.bucket_name
}

output "region" {
  value = local.region
}

output "psql" {
  description = "Conexión con psql (la contraseña se pide o se pasa en PGPASSWORD)"
  value       = "psql \"host=${aws_db_instance.retail.address} port=${aws_db_instance.retail.port} dbname=${local.db_name} user=${aws_db_instance.retail.username} sslmode=require\""
}
