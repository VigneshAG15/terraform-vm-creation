terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# =========================================================
# Resource Group – auto-detect or create
# =========================================================
data "azurerm_resource_group" "existing_rg" {
  name = var.resource_group
}

resource "azurerm_resource_group" "rg" {
  count    = try(data.azurerm_resource_group.existing_rg.name, null) == null ? 1 : 0
  name     = var.resource_group
  location = var.location
}

locals {
  rg_name     = coalesce(try(data.azurerm_resource_group.existing_rg.name, null), try(azurerm_resource_group.rg[0].name, null))
  rg_location = coalesce(try(data.azurerm_resource_group.existing_rg.location, null), try(azurerm_resource_group.rg[0].location, var.location))

  # -------------------------------------------------------
  # Zone handling – true only when user picks 1/2/3
  # -------------------------------------------------------
  use_zone = contains(["1", "2", "3"], var.availability_zone)

  # -------------------------------------------------------
  # Disk size – Windows images need at least 128 GiB
  # -------------------------------------------------------
  disk_size_gb = var.os_type == "Windows" ? max(var.disk_size, 128) : var.disk_size
}

# =========================================================
# Virtual Network & Subnet (shared per environment)
# =========================================================
resource "azurerm_virtual_network" "vnet" {
  name                = "${var.environment}-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = local.rg_location
  resource_group_name = local.rg_name
}

resource "azurerm_subnet" "subnet" {
  name                 = "${var.environment}-subnet"
  resource_group_name  = local.rg_name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = ["10.0.1.0/24"]
}

# =========================================================
# Public IP – Basic (regional) or Standard (zonal)
# =========================================================
resource "azurerm_public_ip" "vm_ip" {
  count               = var.number_of_vms
  name                = "${var.environment}-vm-${count.index}-ip"
  location            = local.rg_location
  resource_group_name = local.rg_name

  # Dynamic allocation for Basic, Static for Standard
  allocation_method = local.use_zone ? "Static" : "Dynamic"
  sku               = local.use_zone ? "Standard" : "Basic"
  sku_tier          = "Regional"

  # Only set zones when we really need them
  zones = local.use_zone ? [var.availability_zone] : null
}

# =========================================================
# Network Interface
# =========================================================
resource "azurerm_network_interface" "vm_nic" {
  count               = var.number_of_vms
  name                = "${var.environment}-vm-${count.index}-nic"
  location            = local.rg_location
  resource_group_name = local.rg_name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.subnet.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.vm_ip[count.index].id
  }
}

# =========================================================
# LINUX VMs (Conditional)
# =========================================================
resource "azurerm_linux_virtual_machine" "linux_vm" {
  count                 = var.os_type == "Linux" ? var.number_of_vms : 0
  name                  = "${var.environment}-vm-${count.index}"
  location              = local.rg_location
  resource_group_name   = local.rg_name
  size                  = var.vm_size
  admin_username        = "azureuser"
  admin_password        = "P@ssword1234!"
  network_interface_ids = [azurerm_network_interface.vm_nic[count.index].id]

  os_disk {
    name                 = "${var.environment}-osdisk-${count.index}"
    caching              = "ReadWrite"
    storage_account_type = var.disk_type
    disk_size_gb         = local.disk_size_gb
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = var.os_version_details == "Ubuntu2204" ? "0001-com-ubuntu-server-jammy" : "0001-com-ubuntu-server-focal"
    sku       = var.os_version_details == "Ubuntu2204" ? "22_04-lts" : "20_04-lts"
    version   = "latest"
  }

  disable_password_authentication = false

  # ---- zone only when requested ----
  zone = local.use_zone ? var.availability_zone : null

  lifecycle {
    replace_triggered_by = [
      azurerm_network_interface.vm_nic[count.index],
      azurerm_public_ip.vm_ip[count.index]
    ]
  }

  depends_on = [
    azurerm_network_interface.vm_nic,
    azurerm_public_ip.vm_ip
  ]

  tags = {
    Environment = var.environment
    VM_Series   = var.vm_series
    OS_Name     = "Linux"
    OS_Version  = var.os_version_details
  }
}

# =========================================================
# WINDOWS VMs (Conditional)
# =========================================================
resource "azurerm_windows_virtual_machine" "windows_vm" {
  count                 = var.os_type == "Windows" ? var.number_of_vms : 0
  name                  = "${var.environment}-vm-${count.index}"
  location              = local.rg_location
  resource_group_name   = local.rg_name
  size                  = var.vm_size
  admin_username        = "azureuser"
  admin_password        = "P@ssword1234!"
  network_interface_ids = [azurerm_network_interface.vm_nic[count.index].id]

  os_disk {
    name                 = "${var.environment}-osdisk-${count.index}"
    caching              = "ReadWrite"
    storage_account_type = var.disk_type
    disk_size_gb         = local.disk_size_gb   # <-- guaranteed >=128
  }

  source_image_reference {
    publisher = "MicrosoftWindowsServer"
    offer     = "WindowsServer"
    sku       = var.os_version_details == "Win2022" ? "2022-datacenter-azure-edition" : "2019-datacenter"
    version   = "latest"
  }

  # ---- zone only when requested ----
  zone = local.use_zone ? var.availability_zone : null

  lifecycle {
    replace_triggered_by = [
      azurerm_network_interface.vm_nic[count.index],
      azurerm_public_ip.vm_ip[count.index]
    ]
  }

  depends_on = [
    azurerm_network_interface.vm_nic,
    azurerm_public_ip.vm_ip
  ]

  tags = {
    Environment = var.environment
    VM_Series   = var.vm_series
    OS_Name     = "Windows"
    OS_Version  = var.os_version_details
  }
}