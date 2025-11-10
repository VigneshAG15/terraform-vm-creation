"""
Script to destroy a specific VM and its associated network resources using Terraform.
Usage: python destroy_vm.py <request_id>
Example: python destroy_vm.py 63148
"""

import sys
import os
import subprocess
import json
import shutil

TF_DIR = "./terraform"

def get_vm_resources_from_tfvars(tfvars_path):
    """Read tfvars file to determine which resources to destroy"""
    with open(tfvars_path, 'r') as f:
        tfvars = json.load(f)
    
    environment = tfvars.get('environment', 'Test')
    os_type = tfvars.get('os_type', 'Windows')
    number_of_vms = tfvars.get('number_of_vms', 1)
    
    return {
        'environment': environment,
        'os_type': os_type,
        'number_of_vms': number_of_vms,
        'tfvars': tfvars
    }

def check_terraform_installed():
    """Check if Terraform is installed"""
    terraform_exe = shutil.which("terraform")
    if not terraform_exe:
        print("[ERROR] Terraform not found on PATH. Please install Terraform.")
        return None
    return terraform_exe

def destroy_vm_resources(request_id, destroy_network=False):
    """Destroy VM and its network resources"""
    tfvars_path = f"{TF_DIR}/generated/request_{request_id}.tfvars.json"
    
    if not os.path.exists(tfvars_path):
        print(f"[ERROR] Terraform vars file not found: {tfvars_path}")
        print(f"[INFO] Available request files:")
        if os.path.exists(f"{TF_DIR}/generated"):
            for file in os.listdir(f"{TF_DIR}/generated"):
                if file.startswith("request_") and file.endswith(".tfvars.json"):
                    print(f"  - {file}")
        return False
    
    terraform_exe = check_terraform_installed()
    if not terraform_exe:
        return False
    
    # Get VM configuration
    vm_config = get_vm_resources_from_tfvars(tfvars_path)
    environment = vm_config['environment']
    os_type = vm_config['os_type']
    number_of_vms = vm_config['number_of_vms']
    
    print(f"[INFO] Destroying VM for request {request_id}")
    print(f"[INFO] Environment: {environment}")
    print(f"[INFO] OS Type: {os_type}")
    print(f"[INFO] Number of VMs: {number_of_vms}")
    
    # Initialize Terraform
    print("\n[INFO] Initializing Terraform...")
    try:
        subprocess.run([terraform_exe, "init", "-input=false"], cwd=TF_DIR, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Terraform init failed: {e}")
        return False
    
    # Build target list for destruction
    targets = []
    network_targets = []
    
    for i in range(number_of_vms):
        # Target the VM (Windows or Linux)
        if os_type == "Windows":
            targets.append(f"azurerm_windows_virtual_machine.windows_vm[{i}]")
        else:
            targets.append(f"azurerm_linux_virtual_machine.linux_vm[{i}]")
        
        # Target associated network resources
        network_targets.append(f"azurerm_network_interface.vm_nic[{i}]")
        network_targets.append(f"azurerm_public_ip.vm_ip[{i}]")
    
    # Add network resources to targets
    targets.extend(network_targets)
    
    # If user wants to destroy VNet/Subnet as well
    if destroy_network:
        targets.append("azurerm_subnet.subnet")
        targets.append("azurerm_virtual_network.vnet")
        print("[WARN] VNet and Subnet will also be destroyed!")
    
    # Step 1: Preview destruction plan
    print(f"\n[INFO] Previewing destruction plan...")
    print("[INFO] This will show what resources will be destroyed.")
    
    plan_cmd = [terraform_exe, "plan", "-destroy", "-var-file", f"generated/request_{request_id}.tfvars.json", "-input=false"]
    for target in targets:
        plan_cmd.extend(["-target", target])
    
    try:
        result = subprocess.run(plan_cmd, cwd=TF_DIR, text=True)
        if result.returncode != 0:
            print(f"[ERROR] Terraform plan failed with return code {result.returncode}")
            return False
        
        # Ask for confirmation
        print("\n" + "="*60)
        print("REVIEW THE PLAN ABOVE CAREFULLY")
        print("="*60)
        confirm = input("\nDo you want to proceed with destruction? (yes/no): ").strip().lower()
        
        if confirm != "yes":
            print("[INFO] Destruction cancelled by user.")
            return False
        
    except Exception as e:
        print(f"[ERROR] Error running terraform plan: {e}")
        return False
    
    # Step 2: Execute destruction
    print(f"\n[INFO] Destroying resources...")
    destroy_cmd = [terraform_exe, "destroy", "-var-file", f"generated/request_{request_id}.tfvars.json", "-input=false"]
    for target in targets:
        destroy_cmd.extend(["-target", target])
    
    print("[INFO] You will be prompted to confirm destruction. Type 'yes' to proceed.")
    
    try:
        result = subprocess.run(destroy_cmd, cwd=TF_DIR, check=True)
        print(f"\n[SUCCESS] VM and associated resources destroyed for request {request_id}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Terraform destroy failed: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python destroy_vm.py <request_id> [--destroy-network]")
        print("Example: python destroy_vm.py 63148")
        print("Example: python destroy_vm.py 63148 --destroy-network  # Also destroys VNet/Subnet")
        sys.exit(1)
    
    request_id = sys.argv[1]
    destroy_network = "--destroy-network" in sys.argv
    
    if destroy_network:
        print("[WARN] You have chosen to destroy VNet and Subnet as well.")
        print("[WARN] Make sure no other VMs are using these network resources!")
        confirm = input("Are you sure? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("[INFO] Cancelled.")
            sys.exit(0)
    
    success = destroy_vm_resources(request_id, destroy_network)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

