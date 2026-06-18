output "repository_url" {
  description = "Full ECR repository URL (use as Docker image prefix)"
  value       = module.ecr.repository_url
}
