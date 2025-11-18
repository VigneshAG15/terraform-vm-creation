# versions.tf
terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.116.0"   # Use 3.x for stability (4.0 has breaking changes)
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # This is ignored in Terraform Cloud — safe to keep for local testing
  backend "remote" {
    organization = "ArcheGlobal-AG"
    workspaces {
      name = "auto-vm-creation"
    }
  }
}