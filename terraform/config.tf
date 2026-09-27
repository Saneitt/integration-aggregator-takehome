resource "vault_generic_endpoint" "oauthapp_config" {
  path                 = "${vault_mount.oauthapp.path}/config"
  ignore_absent_fields = true
  data_json = jsonencode({
    tune_provider_timeout_seconds       = var.tune_provider_timeout_seconds
    tune_refresh_check_interval_seconds = var.tune_refresh_check_interval_seconds
    tune_reap_check_interval_seconds    = var.tune_reap_check_interval_seconds
  })
}