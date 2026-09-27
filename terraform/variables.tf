variable "openbao_addr" {
  description = "OpenBao API address used by Terraform."
  type        = string
  default     = "http://127.0.0.1:18200"
}

variable "mount_path" {
  description = "Path at which oauthapp is mounted."
  type        = string
  default     = "oauthapp"
  validation {
    condition     = can(regex("^[a-z][a-z0-9/-]*$", var.mount_path))
    error_message = "mount_path must contain lowercase path segments."
  }
}

variable "plugin_name" {
  type    = string
  default = "oauthapp"
}

variable "plugin_command" {
  type    = string
  default = "oauthapp"
}

variable "plugin_version" {
  type    = string
  default = "v3.4.0"
}

variable "plugin_sha256" {
  description = "SHA-256 of the oauthapp plugin binary."
  type        = string
  default     = "8eee6499f7bcbcd3fabdb197d0e4a823e9c87de2a1d31be2e7bf5666685c7851"
  validation {
    condition     = can(regex("^[0-9a-fA-F]{64}$", var.plugin_sha256))
    error_message = "plugin_sha256 must be a 64-character hexadecimal digest."
  }
}

variable "kubernetes_host" {
  description = "In-cluster Kubernetes API endpoint used by OpenBao auth."
  type        = string
  default     = "https://kubernetes.default.svc"
}

variable "service_namespace" {
  type    = string
  default = "aggregator"
}

variable "service_account" {
  type    = string
  default = "integration-aggregator"
}

variable "token_audience" {
  type    = string
  default = "openbao"
}

variable "token_ttl" {
  type    = number
  default = 900
  validation {
    condition     = var.token_ttl > 0 && var.token_ttl <= 3600
    error_message = "token_ttl must be between 1 and 3600 seconds."
  }
}

variable "token_max_ttl" {
  type    = number
  default = 3600
  validation {
    condition     = var.token_max_ttl >= var.token_ttl && var.token_max_ttl <= 3600
    error_message = "token_max_ttl must be >= token_ttl and at most 3600 seconds."
  }
}

variable "tune_provider_timeout_seconds" {
  type    = number
  default = 30
}

variable "tune_refresh_check_interval_seconds" {
  type    = number
  default = 60
}

variable "tune_reap_check_interval_seconds" {
  type    = number
  default = 300
}