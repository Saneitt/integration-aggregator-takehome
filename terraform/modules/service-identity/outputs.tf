output "policy_document" {
  value = vault_policy.this.policy
}

output "bound_service_accounts" {
  value = tolist(vault_kubernetes_auth_backend_role.this.bound_service_account_names)
}

output "bound_namespaces" {
  value = tolist(vault_kubernetes_auth_backend_role.this.bound_service_account_namespaces)
}

output "role_name" {
  value = vault_kubernetes_auth_backend_role.this.role_name
}

output "policy_name" {
  value = vault_policy.this.name
}
