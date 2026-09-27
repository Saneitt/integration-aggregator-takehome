terraform {
  required_version = ">= 1.9.0"

  required_providers {
    vault = {
      source  = "hashicorp/vault"
      version = "~> 5.12"
    }
  }

  # State is stored as a Kubernetes Secret in the OpenBao namespace and is
  # removed with the local cluster. See scripts/openbao-configure.sh.
  backend "kubernetes" {}
}