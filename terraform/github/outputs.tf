output "repository_url" {
  description = "HTTPS URL of the GitHub repository"
  value       = github_repository.course_repo.html_url
}

output "repository_ssh_url" {
  description = "SSH clone URL of the GitHub repository"
  value       = github_repository.course_repo.ssh_clone_url
}

output "repository_id" {
  description = "GitHub repository node ID"
  value       = github_repository.course_repo.node_id
}
