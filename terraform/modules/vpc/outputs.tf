output "vpc_id" {
  description = "ID of the created VPC"
  value       = module.vpc.vpc_id
}

output "private_subnets" {
  description = "List of private subnet IDs (EKS nodes live here)"
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "List of public subnet IDs (load balancers live here)"
  value       = module.vpc.public_subnets
}
