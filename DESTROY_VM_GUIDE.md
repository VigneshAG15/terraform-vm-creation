# Guide to Destroy a Specific VM and Network Resources

This guide explains how to delete a specific VM and its associated network resources using Terraform.

## Prerequisites

1. Terraform is installed and available in your PATH
2. You have the `terraform` directory with your Terraform configuration
3. You know the request ID (e.g., `63148`) for the VM you want to delete
4. The corresponding `request_<ID>.tfvars.json` file exists in `terraform/generated/`

## Method 1: Using the Python Script (Recommended)

The easiest way is to use the provided `destroy_vm.py` script:

### Basic Usage (VM, NIC, and Public IP only)

```bash
python destroy_vm.py 63148
```

This will:
- Destroy the VM (Windows or Linux)
- Destroy the associated Network Interface (NIC)
- Destroy the associated Public IP
- **Keep** the VNet and Subnet (in case other VMs are using them)

### Destroy Everything Including Network

If you want to also destroy the VNet and Subnet:

```bash
python destroy_vm.py 63148 --destroy-network
```

**⚠️ Warning:** Only use this if no other VMs are using the same VNet/Subnet!

## Method 2: Manual Terraform Commands

If you prefer to run Terraform commands manually:

### Step 1: Navigate to Terraform Directory

```bash
cd terraform
```

### Step 2: Initialize Terraform (if needed)

```bash
terraform init
```

### Step 3: Preview What Will Be Destroyed

**For PowerShell (Windows):**

For a Windows VM (request 63148, VM index 0):

```powershell
terraform plan -destroy -var-file="generated/request_63148.tfvars.json" -target="azurerm_windows_virtual_machine.windows_vm[0]" -target="azurerm_network_interface.vm_nic[0]" -target="azurerm_public_ip.vm_ip[0]"
```

For a Linux VM:

```powershell
terraform plan -destroy -var-file="generated/request_63148.tfvars.json" -target="azurerm_linux_virtual_machine.linux_vm[0]" -target="azurerm_network_interface.vm_nic[0]" -target="azurerm_public_ip.vm_ip[0]"
```

**For Bash/Linux/Mac:**

For a Windows VM (request 63148, VM index 0):

```bash
terraform plan -destroy -var-file=generated/request_63148.tfvars.json \
  -target=azurerm_windows_virtual_machine.windows_vm[0] \
  -target=azurerm_network_interface.vm_nic[0] \
  -target=azurerm_public_ip.vm_ip[0]
```

For a Linux VM:

```bash
terraform plan -destroy -var-file=generated/request_63148.tfvars.json \
  -target=azurerm_linux_virtual_machine.linux_vm[0] \
  -target=azurerm_network_interface.vm_nic[0] \
  -target=azurerm_public_ip.vm_ip[0]
```

### Step 4: Destroy the Resources

After reviewing the plan, execute the destroy:

**For PowerShell (Windows):**

For Windows VM:
```powershell
terraform destroy -var-file="generated/request_63148.tfvars.json" -target="azurerm_windows_virtual_machine.windows_vm[0]" -target="azurerm_network_interface.vm_nic[0]" -target="azurerm_public_ip.vm_ip[0]"
```

For Linux VM:
```powershell
terraform destroy -var-file="generated/request_63148.tfvars.json" -target="azurerm_linux_virtual_machine.linux_vm[0]" -target="azurerm_network_interface.vm_nic[0]" -target="azurerm_public_ip.vm_ip[0]"
```

**For Bash/Linux/Mac:**

For Windows VM:
```bash
terraform destroy -var-file=generated/request_63148.tfvars.json \
  -target=azurerm_windows_virtual_machine.windows_vm[0] \
  -target=azurerm_network_interface.vm_nic[0] \
  -target=azurerm_public_ip.vm_ip[0]
```

For Linux VM:
```bash
terraform destroy -var-file=generated/request_63148.tfvars.json \
  -target=azurerm_linux_virtual_machine.linux_vm[0] \
  -target=azurerm_network_interface.vm_nic[0] \
  -target=azurerm_public_ip.vm_ip[0]
```

### Step 5: (Optional) Destroy VNet and Subnet

**⚠️ Only do this if no other VMs are using the VNet/Subnet!**

**PowerShell:**
```powershell
terraform destroy -var-file="generated/request_63148.tfvars.json" -target="azurerm_subnet.subnet" -target="azurerm_virtual_network.vnet"
```

**Bash:**
```bash
terraform destroy -var-file=generated/request_63148.tfvars.json \
  -target=azurerm_subnet.subnet \
  -target=azurerm_virtual_network.vnet
```

## Understanding Resource Names

Based on your Terraform configuration:

- **VM Name**: `{environment}-vm-{index}` (e.g., `Test-vm-0`)
- **NIC Name**: `{environment}-vm-{index}-nic` (e.g., `Test-vm-0-nic`)
- **Public IP Name**: `{environment}-vm-{index}-ip` (e.g., `Test-vm-0-ip`)
- **VNet Name**: `{environment}-vnet` (e.g., `Test-vnet`)
- **Subnet Name**: `{environment}-subnet` (e.g., `Test-subnet`)

## Important Notes

1. **Shared Resources**: VNet and Subnet are shared across all VMs in the same environment. If you have multiple VMs in the "Test" environment, they all share the same VNet and Subnet. Be careful when destroying these!

2. **VM Index**: If `number_of_vms` was greater than 1, you may need to destroy multiple VM instances. The index starts at 0, so for 3 VMs, you'd have indices 0, 1, and 2.

3. **Dependencies**: Terraform will automatically handle dependencies. When you destroy a VM, it will also destroy the associated NIC and Public IP if you target them.

4. **State File**: Make sure your `terraform.tfstate` file is up to date. If you've made changes outside of Terraform, you may need to run `terraform refresh` first.

## Troubleshooting

### Error: Resource not found in state

If you get an error that a resource is not found, check:
- The correct request ID
- The VM index (usually 0 for single VM deployments)
- The OS type (Windows vs Linux)

### Error: Cannot destroy VNet/Subnet

If you can't destroy the VNet/Subnet, it's likely because other resources are still using them. Make sure all VMs using that network are destroyed first.

### Multiple VMs from Same Request

If a request created multiple VMs (e.g., `number_of_vms: 3`), you'll need to destroy each one:

**PowerShell:**
```powershell
# Destroy all VMs from request 63148
terraform destroy -var-file=generated/request_63148.tfvars.json -target=azurerm_windows_virtual_machine.windows_vm[0] -target=azurerm_windows_virtual_machine.windows_vm[1] -target=azurerm_windows_virtual_machine.windows_vm[2] -target=azurerm_network_interface.vm_nic[0] -target=azurerm_network_interface.vm_nic[1] -target=azurerm_network_interface.vm_nic[2] -target=azurerm_public_ip.vm_ip[0] -target=azurerm_public_ip.vm_ip[1] -target=azurerm_public_ip.vm_ip[2]
```

**Bash:**
```bash
# Destroy all VMs from request 63148
terraform destroy -var-file=generated/request_63148.tfvars.json \
  -target=azurerm_windows_virtual_machine.windows_vm[0] \
  -target=azurerm_windows_virtual_machine.windows_vm[1] \
  -target=azurerm_windows_virtual_machine.windows_vm[2] \
  -target=azurerm_network_interface.vm_nic[0] \
  -target=azurerm_network_interface.vm_nic[1] \
  -target=azurerm_network_interface.vm_nic[2] \
  -target=azurerm_public_ip.vm_ip[0] \
  -target=azurerm_public_ip.vm_ip[1] \
  -target=azurerm_public_ip.vm_ip[2]
```

## Verification

After destruction, verify the resources are deleted:

1. Check Azure Portal
2. Or run: `terraform state list` to see remaining resources
3. Or run: `terraform show` to inspect the current state

