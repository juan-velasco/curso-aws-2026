output "bucket_name" {
  value = local.bucket_name
}

output "region" {
  value = local.region
}

output "workgroup" {
  value = aws_athena_workgroup.curso.name
}

output "crawler" {
  value = aws_glue_crawler.bronze_cdc.name
}

output "base_datos_bronze" {
  value = aws_glue_catalog_database.bronze.name
}

output "base_datos_silver" {
  value = aws_glue_catalog_database.silver.name
}
