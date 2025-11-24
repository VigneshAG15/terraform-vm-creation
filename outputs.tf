###############################################################
# Public IPs – Reliable (uses data source to fetch final IP)
###############################################################
output "vm_public_ips" {
  description = "Public IP addresses of created VMs"
  value       = data.azurerm_public_ip.vm_ip_data[*].ip_address
}

###############################################################
# Private IPs – Helpful for internal access / debugging
###############################################################
output "vm_private_ips" {
  description = "Private IP addresses of created VMs"
  value = azurerm_network_interface.vm_nic[*].ip_configuration[0].private_ip_address
}

###############################################################
# VM Names – Works for Linux-only, Windows-only, or mixed
###############################################################
output "vm_names" {
  description = "Names of all created VMs"
  value = concat(
    try(azurerm_linux_virtual_machine.linux_vm[*].name, []),
    try(azurerm_windows_virtual_machine.windows_vm[*].name, [])
  )
}

###############################################################
# Admin credentials
###############################################################
output "admin_username" {
  description = "Admin username for VMs"
  value       = "azureuser"
}

output "admin_password" {
  description = "Auto-generated admin password"
  value       = random_password.vm_password.result
  sensitive   = true
}

###############################################################
# Resource Group Name
###############################################################
output "resource_group_name" {
  description = "Resource group where resources are created"
  value       = local.rg_name
}
