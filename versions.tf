# versions.tf
terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.116.0"   # or "~> 4.0" if you really want v4
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # This backend block is IGNORED when using Terraform Cloud
  # (it's only for local runs — safe to keep)
  backend "remote" {
    organization = "ArcheGlobal-AG"
    workspaces {
      name = "auto-vm-creation"
    }
  }
}