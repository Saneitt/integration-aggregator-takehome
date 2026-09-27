resource "vault_plugin" "oauthapp" {
  type    = "secret"
  name    = var.plugin_name
  command = var.plugin_command
  version = var.plugin_version
  sha256  = var.plugin_sha256
}