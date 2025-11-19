# main.tf — ONLY resources, locals, and provider
# "If exists → use it, else → create it" for EVERYTHING

provider "azurerm" {
  features {}
}

# =========================================================
# Resource Group – use existing or create
# =========================================================
data "azurerm_resource_group" "existing_rg" {
  name = var.resource_group
}

resource "azurerm_resource_group" "rg" {
  count    = try(data.azurerm_resource_group.existing_rg.id, null) == null ? 1 : 0
  name     = var.resource_group
  location = var.location
}

locals {
  rg_name     = coalesce(try(data.azurerm_resource_group.existing_rg.name, null), azurerm_resource_group.rg[0].name)
  rg_location = coalesce(try(data.azurerm_resource_group.existing_rg.location, null), azurerm_resource_group.rg[0].location)

  use_zone     = contains(["1", "2", "3"], var.availability_zone)
  disk_size_gb = var.os_type == "Windows" ? max(var.disk_size, 128) : var.disk_size
  admin_password = random_password.vm_password.result
}

# =========================================================
# Random Secure Password
# =========================================================
resource "random_password" "vm_password" {
  length           = 16
  special          = true
  override_special = "!@#$%&*()-_=+"
  min_lower        = 1
  min_upper        = 1
  min_numeric      = 1
  min_special      = 1
}

# =========================================================
# Virtual Network – use existing or create
# =========================================================
data "azurerm_virtual_network" "existing_vnet" {
  name                = "${var.environment}-vnet"
  resource_group_name = local.rg_name
}

resource "azurerm_virtual_network" "vnet" {
  count               = try(data.azurerm_virtual_network.existing_vnet.id, null) == null ? 1 : 0
  name                = "${var.environment}-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = local.rg_location
  resource_group_name = local.rg_name
}

locals {
  vnet_name = try(data.azurerm_virtual_network.existing_vnet.name, azurerm_virtual_network.vnet[0].name)
  vnet_id   = try(data.azurerm_virtual_network.existing_vnet.id, azurerm_virtual_network.vnet[0].id)
}

# =========================================================
# Subnet – use existing or create
# =========================================================
data "azurerm_subnet" "existing_subnet" {
  name                 = "${var.environment}-subnet"
  virtual_network_name = local.vnet_name
  resource_group_name  = local.rg_name
}

resource "azurerm_subnet" "subnet" {
  count                = try(data.azurerm_subnet.existing_subnet.id, null) == null ? 1 : 0
  name                 = "${var.environment}-subnet"
  resource_group_name  = local.rg_name
  virtual_network_name = local.vnet_name
  address_prefixes     = ["10.0.1.0/24"]
}

locals {
  subnet_id = try(data.azurerm_subnet.existing_subnet.id, azurerm_subnet.subnet[0].id)
}

# =========================================================
# Public IP – use existing or create (per VM)
# =========================================================
data "azurerm_public_ip" "existing_pip" {
  for_each            = toset([for i in range(var.number_of_vms) : tostring(i)])
  name                = "${var.environment}-vm-${each.value}-ip"
  resource_group_name = local.rg_name
}

resource "azurerm_public_ip" "vm_ip" {
  for_each            = toset([for i in range(var.number_of_vms) : tostring(i)])
  count               = try(data.azurerm_public_ip.existing_pip[each.value].id, null) == null ? 1 : 0
  name                = "${var.environment}-vm-${each.value}-ip"
  location            = local.rg_location
  resource_group_name = local.rg_name
  allocation_method   = local.use_zone ? "Static" : "Dynamic"
  sku                 = local.use_zone ? "Standard" : "Basic"
  sku_tier            = "Regional"
  zones               = local.use_zone ? [var.availability_zone] : null
}

locals {
  public_ip_ids = {
    for i in range(var.number_of_vms) :
    i => try(data.azurerm_public_ip.existing_pip[tostring(i)].id, azurerm_public_ip.vm_ip[tostring(i)][0].id)
  }
}

# =========================================================
# Network Interface – use existing or create (per VM)
# =========================================================
data "azurerm_network_interface" "existing_nic" {
  for_each            = toset([for i in range(var.number_of_vms) : tostring(i)])
  name                = "${var.environment}-vm-${each.value}-nic"
  resource_group_name = local.rg_name
}

resource "azurerm_network_interface" "vm_nic" {
  for_each            = toset([for i in range(var.number_of_vms) : tostring(i)])
  count               = try(data.azurerm_network_interface.existing_nic[each.value].id, null) == null ? 1 : 0

  name                = "${var.environment}-vm-${each.value}-nic"
  location            = local.rg_location
  resource_group_name = local.rg_name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = local.subnet_id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = local.public_ip_ids[tonumber(each.value)]
  }
}

locals {
  nic_ids = {
    for i in range(var.number_of_vms) :
    i => try(data.azurerm_network_interface.existing_nic[tostring(i)].id, azurerm_network_interface.vm_nic[tostring(i)][0].id)
  }
}

# =========================================================
# LINUX VMs – use existing or create
# =========================================================
data "azurerm_linux_virtual_machine" "existing_linux_vm" {
  for_each = var.os_type == "Linux" ? { for i in range(var.number_of_vms) : i => i } : {}
  name                = "${var.environment}-vm-${each.value}"
  resource_group_name = local.rg_name
}

resource "azurerm_linux_virtual_machine" "linux_vm" {
  for_each = var.os_type == "Linux" ? {
    for i in range(var.number_of_vms) :
    i => i
    if try(data.azurerm_linux_virtual_machine.existing_linux_vm[tostring(i)].id, null) == null
  } : {}

  name                            = "${var.environment}-vm-${each.value}"
  location                        = local.rg_location
  resource_group_name             = local.rg_name
  size                            = var.vm_size
  admin_username                  = "azureuser"
  admin_password                  = local.admin_password
  disable_password_authentication = false
  network_interface_ids           = [local.nic_ids[each.value]]

  os_disk {
    name                 = "${var.environment}-osdisk-${each.value}"
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

  zone = local.use_zone ? var.availability_zone : null

  tags = {
    Environment = var.environment
    VM_Series   = var.vm_series
    OS_Name     = "Linux"
    OS_Version  = var.os_version_details
  }
}

# =========================================================
# WINDOWS VMs – use existing or create
# =========================================================
data "azurerm_windows_virtual_machine" "existing_windows_vm" {
  for_each = var.os_type == "Windows" ? { for i in range(var.number_of_vms) : i => i } : {}
  name                = "${var.environment}-vm-${each.value}"
  resource_group_name = local.rg_name
}

resource "azurerm_windows_virtual_machine" "windows_vm" {
  for_each = var.os_type == "Windows" ? {
    for i in range(var.number_of_vms) :
    i => i
    if try(data.azurerm_windows_virtual_machine.existing_windows_vm[tostring(i)].id, null) == null
  } : {}

  name                = "${var.environment}-vm-${each.value}"
  location            = local.rg_location
  resource_group_name = local.rg_name
  size                = var.vm_size
  admin_username      = "azureuser"
  admin_password      = local.admin_password
  network_interface_ids = [local.nic_ids[each.value]]

  os_disk {
    name                 = "${var.environment}-osdisk-${each.value}"
    caching              = "ReadWrite"
    storage_account_type = var.disk_type
    disk_size_gb         = local.disk_size_gb
  }

  source_image_reference {
    publisher = "MicrosoftWindowsServer"
    offer     = "WindowsServer"
    sku       = var.os_version_details == "Win2022" ? "2022-datacenter-azure-edition" : "2019-datacenter"
    version   = "latest"
  }

  zone = local.use_zone ? var.availability_zone : null

  tags = {
    Environment = var.environment
    VM_Series   = var.vm_series
    OS_Name     = "Windows"
    OS_Version  = var.os_version_details
  }
}