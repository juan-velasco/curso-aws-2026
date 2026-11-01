output "region" {
  value = local.region
}

output "bucket_name" {
  value = data.terraform_remote_state.base.outputs.bucket_name
}

output "dominio_id" {
  value = aws_sagemaker_domain.curso.id
}

output "perfil" {
  value = aws_sagemaker_user_profile.profesor.user_profile_name
}

output "rol_ejecucion_arn" {
  value = aws_iam_role.sagemaker.arn
}

output "url_studio" {
  value = aws_sagemaker_domain.curso.url
}

output "quicksight_dataset_id" {
  value = var.quicksight_activo ? aws_quicksight_data_set.prevision[0].data_set_id : ""
}
