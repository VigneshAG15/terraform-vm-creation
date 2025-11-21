# outputs.tf
output "vm_public_ips" {
  description = "Public IP addresses of created VMs"
  value = concat(
    azurerm_linux_virtual_machine.linux_vm[*].public_ip_address,
    azurerm_windows_virtual_machine.windows_vm[*].public_ip_address
  )
}

output "admin_username" {
  description = "Admin username for VMs"
  value       = "azureuser"
}

output "admin_password" {
  description = "Auto-generated admin password"
  value       = random_password.vm_password.result
  sensitive   = true
}

output "vm_names" {
  description = "Names of created VMs"
  value = concat(
    azurerm_linux_virtual_machine.linux_vm[*].name,
    azurerm_windows_virtual_machine.windows_vm[*].name
  )
}

output "resource_group_name" {
  value = local.rg_name
}