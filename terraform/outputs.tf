output "vm_public_ip" {
  description = "Public IP address of the created VM"
  value       = yandex_compute_instance.vm.network_interface[0].nat_ip_address
}

output "ssh_command" {
  description = "Command to SSH into the VM"
  value       = "ssh ${var.ssh_user}@${yandex_compute_instance.vm.network_interface[0].nat_ip_address}"
}

output "vm_id" {
  description = "Internal ID of the created VM"
  value       = yandex_compute_instance.vm.id
}
