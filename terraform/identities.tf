module "integration_aggregator" {
  source          = "./modules/service-identity"
  name            = "integration-aggregator"
  auth_backend    = vault_auth_backend.kubernetes.path
  namespace       = var.service_namespace
  service_account = var.service_account
  audience        = var.token_audience
  token_ttl       = var.token_ttl
  token_max_ttl   = var.token_max_ttl
  policy_hcl = templatefile("${path.module}/policies/integration-aggregator.hcl.tftpl", {
    mount = vault_mount.oauthapp.path
  })
}