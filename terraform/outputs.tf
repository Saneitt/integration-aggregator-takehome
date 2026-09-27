output "oauthapp_mount_path" {
  value       = vault_mount.oauthapp.path
  description = "OpenBao path at which the oauthapp secrets engine is mounted."
}

output "kubernetes_auth_role" {
  value       = module.integration_aggregator.role_name
  description = "Kubernetes auth role used by the service."
}

output "service_policy_name" {
  value       = module.integration_aggregator.policy_name
  description = "Least-privilege OpenBao policy attached to the service role."
}