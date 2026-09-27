resource "vault_policy" "this" {
  name   = var.name
  policy = var.policy_hcl
}

resource "vault_kubernetes_auth_backend_role" "this" {
  backend                          = var.auth_backend
  role_name                        = var.name
  bound_service_account_names      = [var.service_account]
  bound_service_account_namespaces = [var.namespace]
  audience                         = var.audience
  token_policies                   = [vault_policy.this.name]
  token_ttl                        = var.token_ttl
  token_max_ttl                    = var.token_max_ttl
  token_no_default_policy          = true
}