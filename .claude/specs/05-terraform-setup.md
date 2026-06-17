# Spec: Terraform Setup

## Overview
This step provisions the AWS infrastructure required to run the ML serving API on Kubernetes.
Using Terraform, we create a VPC with public and private subnets, an EKS cluster inside that
VPC, a managed node group for worker nodes, IAM roles for both the cluster control plane and
the nodes, and an ECR repository to hold the Docker image built in the next step. All
infrastructure is organised as **local Terraform modules** (`terraform/modules/vpc`,
`terraform/modules/eks`, `terraform/modules/ecr`) — each one wraps the corresponding
`terraform-aws-modules` community module. The root `main.tf` calls all three local modules and
wires their outputs together (VPC subnet IDs flow into EKS).

## Depends on
- **Step 04 — AWS Kubernetes MCP Setup**: `aws configure` must be working (credentials valid);
  the `terraform` MCP server must be connected so resource arguments can be looked up inline.
- **Local prerequisites**:
  - Terraform ≥ 1.5 (`brew install terraform`)
  - AWS CLI v2 (`aws sts get-caller-identity` returns a valid account ID)
  - `kubectl` installed (used in later steps, but kubeconfig is generated here)

## Routes
No new routes.

## Templates
- **Create:** None
- **Modify:** None

## Files to create

```
terraform/                          ← run all terraform commands from here
├── main.tf
├── variables.tf
├── outputs.tf
├── terraform.tfvars                ← gitignored; concrete values
└── modules/
    ├── vpc/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── eks/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    └── ecr/
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

## Files to change
- `.gitignore` — append a `# Terraform` section (see below)

## New dependencies
No new pip packages.

External tooling:
- `terraform` ≥ 1.5 — `brew install terraform`

Community modules downloaded automatically by `terraform init`:
- `terraform-aws-modules/vpc/aws` v5.21.0
- `terraform-aws-modules/eks/aws` v20.37.2 (pulls `kms` v2.1.0 as a sub-module)
- `terraform-aws-modules/ecr/aws` v2.4.0

---

## Implementation — exact file contents

### `terraform/main.tf`
```hcl
terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local state is fine for solo development.
  # For team/production: use an S3 backend with DynamoDB locking.
}

provider "aws" {
  region = var.aws_region
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
```

### `terraform/variables.tf`
```hcl
variable "aws_region" {
  description = "AWS region to deploy all resources"
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "Name of the EKS cluster and prefix for related resources"
  default     = "ml-serving-cluster"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  default     = "10.0.0.0/16"
}

variable "node_instance_type" {
  description = "EC2 instance type for EKS worker nodes"
  default     = "t3.medium"
}

variable "node_desired_size" {
  description = "Desired number of worker nodes"
  default     = 2
}

variable "node_max_size" {
  description = "Maximum number of worker nodes"
  default     = 5
}

variable "ecr_repo_name" {
  description = "Name of the ECR repository for the ML API Docker image"
  default     = "ml-api"
}
```

### `terraform/outputs.tf`
```hcl
output "cluster_name" {
  description = "Name of the EKS cluster"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "Kubernetes API server endpoint"
  value       = module.eks.cluster_endpoint
}

output "ecr_repo_url" {
  description = "ECR repository URL — use as the Docker image prefix"
  value       = module.ecr.repository_url
}

output "kubeconfig_cmd" {
  description = "Run this after apply to configure kubectl"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}
```

### `terraform/terraform.tfvars` (gitignored)
```hcl
aws_region         = "us-east-1"
cluster_name       = "ml-serving-cluster"
node_instance_type = "t3.medium"
node_desired_size  = 2
node_max_size      = 5
ecr_repo_name      = "ml-api"
```

---

### `terraform/modules/vpc/variables.tf`
```hcl
variable "cluster_name" {
  description = "Cluster name — used to prefix the VPC name"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "aws_region" {
  description = "AWS region — used to derive AZ names"
  type        = string
}
```

### `terraform/modules/vpc/main.tf`
```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.cluster_name}-vpc"
  cidr = var.vpc_cidr

  azs             = ["${var.aws_region}a", "${var.aws_region}b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = true   # one NAT GW saves ~$32/month; set false for HA prod
  enable_dns_hostnames = true

  # Required by the AWS Load Balancer Controller to auto-discover subnets
  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }
}
```

### `terraform/modules/vpc/outputs.tf`
```hcl
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
```

---

### `terraform/modules/eks/variables.tf`
```hcl
variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "cluster_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.31"
}

variable "vpc_id" {
  description = "VPC ID where the cluster will be created"
  type        = string
}

variable "subnet_ids" {
  description = "Private subnet IDs for the worker nodes"
  type        = list(string)
}

variable "node_instance_type" {
  description = "EC2 instance type for worker nodes"
  type        = string
  default     = "t3.medium"
}

variable "node_desired_size" {
  description = "Desired number of worker nodes"
  type        = number
  default     = 2
}

variable "node_max_size" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 5
}
```

### `terraform/modules/eks/main.tf`
```hcl
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  vpc_id     = var.vpc_id
  subnet_ids = var.subnet_ids

  # Public endpoint lets kubectl reach the API server from a laptop.
  # In production, restrict cluster_endpoint_public_access_cidrs to a VPN range.
  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    default = {
      instance_types = [var.node_instance_type]
      min_size       = 1
      max_size       = var.node_max_size
      desired_size   = var.node_desired_size

      labels = {
        role = "ml-serving"
      }
    }
  }
}
```

### `terraform/modules/eks/outputs.tf`
```hcl
output "cluster_name" {
  description = "Name of the EKS cluster"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "Kubernetes API server endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_certificate_authority_data" {
  description = "Base64-encoded CA certificate for the cluster"
  value       = module.eks.cluster_certificate_authority_data
}
```

---

### `terraform/modules/ecr/variables.tf`
```hcl
variable "repo_name" {
  description = "Name of the ECR repository"
  type        = string
}
```

### `terraform/modules/ecr/main.tf`
```hcl
module "ecr" {
  source  = "terraform-aws-modules/ecr/aws"
  version = "~> 2.0"

  repository_name                 = var.repo_name
  repository_image_tag_mutability = "MUTABLE"
  repository_image_scan_on_push   = true

  repository_lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = { type = "expire" }
      }
    ]
  })
}
```

### `terraform/modules/ecr/outputs.tf`
```hcl
output "repository_url" {
  description = "Full ECR repository URL (use as Docker image prefix)"
  value       = module.ecr.repository_url
}
```

---

### `.gitignore` additions
```
# Terraform
terraform/.terraform/
terraform/*.tfstate
terraform/*.tfstate.backup
terraform/*.tfvars
terraform/.terraform.lock.hcl
```

---

## Apply sequence
```bash
cd terraform
terraform init      # downloads vpc, eks, ecr community modules + all providers
terraform validate  # "Success! The configuration is valid."
terraform plan      # 55 resources to add
terraform apply     # ~12-15 min (EKS control plane is the bottleneck)
```

After apply:
```bash
terraform output kubeconfig_cmd | bash   # configure kubectl
kubectl get nodes                        # should show 2 Ready t3.medium nodes
terraform output ecr_repo_url           # ECR URI for docker push in Step 06
```

## Cost awareness (us-east-1, on-demand, running 24×7)
| Resource | Monthly |
|---|---|
| EKS control plane | $73.00 |
| EC2 t3.medium × 2 | $60.74 |
| NAT Gateway (hourly + data) | ~$33.30 |
| KMS key + API calls | ~$1.03 |
| CloudWatch Logs | ~$1.18 |
| ECR storage | ~$0.10 |
| **Total** | **~$169/month (~$5.65/day)** |

**Run `terraform destroy` when not actively developing.**

## Definition of done
- [ ] `terraform/modules/vpc/`, `terraform/modules/eks/`, `terraform/modules/ecr/` all exist
      with `main.tf`, `variables.tf`, `outputs.tf` in each
- [ ] `terraform/terraform.tfvars` exists locally (not committed to git)
- [ ] `.gitignore` excludes `*.tfstate*`, `.terraform/`, `*.tfvars`, `.terraform.lock.hcl`
- [ ] `terraform init` completes — downloads vpc, eks, ecr community modules with no errors
- [ ] `terraform validate` passes with "Success! The configuration is valid."
- [ ] `terraform plan` shows **55 resources** to add with no errors
- [ ] `terraform apply` completes successfully
- [ ] `aws eks list-clusters` shows `ml-serving-cluster`
- [ ] `terraform output kubeconfig_cmd | bash` runs without error
- [ ] `kubectl get nodes` shows ≥ 1 Ready node (t3.medium)
- [ ] `aws ecr describe-repositories` shows `ml-api` repository
- [ ] `terraform output ecr_repo_url` returns a valid ECR URI
- [ ] No AWS credentials or account IDs are hardcoded in any `.tf` file
