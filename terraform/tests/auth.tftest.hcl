mock_provider "vault" {}

run "role_is_bound_to_one_service_account" {
  command = plan

  assert {
    condition     = length(module.integration_aggregator.bound_service_accounts) == 1 && contains(module.integration_aggregator.bound_service_accounts, "integration-aggregator")
    error_message = "The auth role must be bound to exactly one ServiceAccount."
  }

  assert {
    condition     = length(module.integration_aggregator.bound_namespaces) == 1 && contains(module.integration_aggregator.bound_namespaces, "aggregator")
    error_message = "The auth role must be bound to exactly one namespace."
  }

  assert {
    condition     = var.token_max_ttl <= 3600
    error_message = "Service tokens must not live longer than one hour."
  }
}
