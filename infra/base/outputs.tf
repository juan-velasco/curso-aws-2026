output "bucket_name" {
  value = aws_s3_bucket.lago.bucket
}

output "bucket_arn" {
  value = aws_s3_bucket.lago.arn
}

output "region" {
  value = var.region
}

output "account_id" {
  value = data.aws_caller_identity.actual.account_id
}
