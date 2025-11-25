# Required: OS Type
variable "os_type" {
  type        = string
  description = "Operating system type: Linux or Windows"
  validation {
    condition     = contains(["Linux", "Windows"], var.os_type)
    error_message = "os_type must be 'Linux' or 'Windows'."
  }
}

# Required: Environment
variable "environment" {
  type        = string
  description = "Deployment environment"
  validation {
    condition     = contains(["Dev", "Test", "Prod"], var.environment)
    error_message = "environment must be one of: Dev, Test, Prod."
  }
}

# Required: VM Size
variable "vm_size" {
  type        = string
  description = "Azure VM size (e.g., Standard_D2ds_v5)"
  validation {
    condition     = startswith(var.vm_size, "Standard_")
    error_message = "vm_size must start with 'Standard_'."
  }
}

# Required: Location
variable "location" {
  type        = string
  description = "Azure region (e.g., centralindia, eastus)"
}

# Required: Disk Type
variable "disk_type" {
  type        = string
  description = "Managed disk storage type"
  default     = "Premium_LRS"
}

# Required: Disk Size
variable "disk_size" {
  type        = number
  description = "OS disk size in GB"
  validation {
    condition     = var.disk_size >= 30
    error_message = "disk_size must be at least 30 GB."
  }
}

# Required: Resource Group Name
variable "resource_group" {
  type        = string
  description = "Name of the resource group"
  validation {
    condition     = can(regex("^[a-zA-Z0-9_-]{1,90}$", var.resource_group))
    error_message = "resource_group must be 1-90 chars: letters, numbers, hyphens, underscores only."
  }
}

# Optional but recommended: OS Version Details (Now Flexible)
variable "os_version_details" {
  type        = string
  description = "OS image identifier. Examples: Ubuntu2204, Win2022, Win2022AzureEdition, CustomImage"

}

# Optional: Availability Zone
variable "availability_zone" {
  type        = string
  description = "Zone for high availability (e.g., Zone 1, Zone 2, Zone 3)"
  default     = null
  validation {
    condition = (
      var.availability_zone == null ||
      contains(["Zone 1", "Zone 2", "Zone 3"], var.availability_zone)
    )
    error_message = "availability_zone must be null or one of: Zone 1, Zone 2, Zone 3."
  }
}

# Optional: Additional metadata (not used in logic, but useful for tagging)
variable "os_name" {
  type        = string
  description = "Human-readable OS name (e.g., Ubuntu, Windows Server)"
  default     = null
}

variable "os_version" {
  type        = string
  description = "OS version for tagging (e.g., 22.04, 2022)"
  default     = null
}

variable "vm_series" {
  type        = string
  description = "VM family (e.g., D-series, B-series)"
  default     = null
}

# Required: Number of VMs
variable "number_of_vms" {
  type        = number
  description = "Number of VMs to create"
  validation {
    condition     = var.number_of_vms >= 1 && var.number_of_vms <= 100
    error_message = "number_of_vms must be between 1 and 100."
  }
}

variable "request_id" {
  type    = string
  default = "unknown"
}
