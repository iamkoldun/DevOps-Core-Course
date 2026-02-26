terraform {
  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
  required_version = ">= 1.9"
}

provider "github" {
  token = var.github_token
}

resource "github_repository" "course_repo" {
  name        = "devops"
  description = "DevOps Engineering: Core Practices — lab assignments"
  visibility  = "public"

  has_issues   = true
  has_wiki     = false
  has_projects = false
  has_downloads = true

  auto_init = false
}
