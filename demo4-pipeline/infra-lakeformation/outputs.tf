output "roles_demo" {
  description = "Roles que asumir con switch role"
  value       = { for k, r in aws_iam_role.demo : k => r.arn }
}

output "url_switch_role" {
  value = { for k, r in aws_iam_role.demo : k => "https://signin.aws.amazon.com/switchrole?account=${local.account_id}&roleName=${k}" }
}
