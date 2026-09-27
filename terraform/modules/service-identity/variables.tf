variable "name" {
  type = string
}

variable "auth_backend" {
  type = string
}

variable "namespace" {
  type = string
}

variable "service_account" {
  type = string
}

variable "audience" {
  type = string
}

variable "token_ttl" {
  type = number
}

variable "token_max_ttl" {
  type = number
}

variable "policy_hcl" {
  type = string
}
