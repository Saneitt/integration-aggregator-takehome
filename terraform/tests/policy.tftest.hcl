mock_provider "vault" {}

run "service_policy_is_least_privilege" {
  command = plan

  assert {
    condition     = !strcontains(module.integration_aggregator.policy_document, "sys/")
    error_message = "The service policy must not grant access under sys/."
  }

  assert {
    condition     = !strcontains(module.integration_aggregator.policy_document, "delete") && !strcontains(module.integration_aggregator.policy_document, "sudo")
    error_message = "The service policy must not grant delete or sudo."
  }

  assert {
    condition     = length(regexall("path ", module.integration_aggregator.policy_document)) == 3
    error_message = "The service policy must contain exactly three path rules."
  }
}
