variable "yc_token" {
  description = "Yandex Cloud OAuth token or IAM token"
  type        = string
  sensitive   = true
}

variable "folder_id" {
  description = "Yandex Cloud folder ID"
  type        = string
}

variable "zone" {
  description = "Yandex Cloud availability zone"
  type        = string
  default     = "ru-central1-a"
}

variable "prefix" {
  description = "Prefix used for naming all created resources"
  type        = string
  default     = "lab04"
}

variable "image_id" {
  description = "Boot disk image ID (Ubuntu 24.04 LTS in ru-central1)"
  type        = string
  default     = "fd8ciuqfa001h8s9sa7i"
}

variable "ssh_user" {
  description = "Username for SSH access"
  type        = string
  default     = "ubuntu"
}

variable "ssh_public_key_path" {
  description = "Local path to the SSH public key file"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed to connect via SSH (restrict to your IP for security)"
  type        = string
  default     = "0.0.0.0/0"
}
