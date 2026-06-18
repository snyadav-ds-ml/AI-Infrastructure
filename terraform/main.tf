terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
  }

  # Local state is fine for solo development.
  # For team/production: use an S3 backend with DynamoDB locking.
}

provider "aws" {
  region = var.aws_region
}

# Helm provider connects to EKS using the aws CLI exec plugin — no static kubeconfig needed.
provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
      command     = "aws"
    }
  }
}

module "vpc" {
  source = "./modules/vpc"

  cluster_name = var.cluster_name
  vpc_cidr     = var.vpc_cidr
  aws_region   = var.aws_region
}

module "eks" {
  source = "./modules/eks"

  cluster_name       = var.cluster_name
  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.private_subnets
  node_instance_type = var.node_instance_type
  node_desired_size  = var.node_desired_size
  node_max_size      = var.node_max_size
}

module "ecr" {
  source = "./modules/ecr"

  repo_name = var.ecr_repo_name
}

module "monitoring" {
  source = "./modules/monitoring"

  namespace              = var.monitoring_namespace
  grafana_admin_password = var.grafana_admin_password

  depends_on = [module.eks]
}
