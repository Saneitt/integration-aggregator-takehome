resource "vault_mount" "oauthapp" {
  path           = var.mount_path
  type           = vault_plugin.oauthapp.name
  plugin_version = vault_plugin.oauthapp.version
  description    = "OAuth token broker powered by openbao-plugin-secrets-oauthapp."
}