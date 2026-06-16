# Spec: AWS Kubernetes MCP Setup

## Overview
This step configures the MCP (Model Context Protocol) servers for AWS and Terraform inside
Claude Code so that subsequent deployment steps (Docker, K8s manifests, monitoring, cost
analysis) can be executed with AI-assisted tooling. Rather than running raw CLI commands
manually, Claude will be able to search AWS documentation, query live AWS pricing, and
generate Terraform infrastructure code through local MCP server processes. This is a
developer-tooling step with no application code changes — all output is configuration files
and verified connectivity.

## Depends on
- **Step 03 — API Setup**: The FastAPI app must be working locally before containerisation and
  cloud deployment are started. MCP setup has no code dependency but logically precedes T5–T8.
- **Local prerequisites** (must be in place before implementation begins):
  - AWS account with IAM credentials configured (`aws configure`)
  - `uv` installed (`brew install uv`) — used to run AWS MCP servers via `uvx`
  - `node` ≥ 18 and `npx` installed — used to run the Terraform MCP server

## Routes
No new routes.

## Templates
- **Create:** None
- **Modify:** None

## Files to change
- `docs/mcp-setup.md` — update server list to reflect current active servers

## Files to create
- `docs/iam-policy.json` — minimum IAM permissions required for AWS MCP servers

## New dependencies
No new pip packages.

External tools run at the system level via `uvx` / `npx` (no install step needed):
- `awslabs.aws-documentation-mcp-server` — run via `uvx`
- `awslabs.aws-pricing-mcp-server` — run via `uvx`
- `awslabs.eks-mcp-server` — run via `uvx`
- `terraform-mcp-server` — run via `npx`

## Implementation notes

### Registering MCP servers
MCP servers are registered via `claude mcp add`, which writes to `~/.claude.json` keyed
by project path. Do **not** use `settings.json` for MCP registration — Claude Code does
not read MCP servers from that file.

```bash
# AWS documentation search
claude mcp add aws-docs \
  -e FASTMCP_LOG_LEVEL=ERROR \
  -- uvx awslabs.aws-documentation-mcp-server@latest

# AWS pricing queries
claude mcp add aws-pricing \
  -e FASTMCP_LOG_LEVEL=ERROR \
  -e AWS_REGION=us-east-1 \
  -- uvx awslabs.aws-pricing-mcp-server@latest

# EKS cluster management — describe clusters, nodes, pods, deployments
claude mcp add eks \
  -e FASTMCP_LOG_LEVEL=ERROR \
  -e AWS_REGION=us-east-1 \
  -- uvx awslabs.eks-mcp-server@latest

# Terraform registry — providers, modules, docs
claude mcp add terraform \
  -- npx -y terraform-mcp-server
```

### What each server provides

| Server | Package | Purpose |
|---|---|---|
| `aws-docs` | `awslabs.aws-documentation-mcp-server` | Search and read AWS documentation inline |
| `aws-pricing` | `awslabs.aws-pricing-mcp-server` | Query live AWS service pricing and cost estimates |
| `eks` | `awslabs.eks-mcp-server` | Manage EKS clusters — describe nodes, pods, deployments, logs |
| `terraform` | `terraform-mcp-server` (npm) | Browse Terraform registry — providers, modules, resource docs |

### Packages that are yanked (do not use)
- `awslabs.core-mcp-server` — yanked; reason: "load individual MCPs"
- `awslabs.cdk-mcp-server` — yanked; superseded by `awslabs.aws-iac-mcp-server`

### IAM permissions required
The `aws-pricing` and `eks` servers call live AWS APIs. Minimum permissions needed:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity",
        "pricing:GetProducts",
        "pricing:DescribeServices",
        "pricing:GetAttributeValues",
        "ce:GetCostAndUsage",
        "ce:GetCostForecast",
        "eks:ListClusters",
        "eks:DescribeCluster",
        "eks:ListNodegroups",
        "eks:DescribeNodegroup",
        "eks:ListFargateProfiles",
        "eks:DescribeFargateProfile",
        "eks:AccessKubernetesApi"
      ],
      "Resource": "*"
    }
  ]
}
```

Save this as `docs/iam-policy.json`.

### Verification steps
After registering, run `claude mcp list` to confirm all three servers are connected.
Then verify each works in a new Claude Code session:

- **aws-docs**: Ask Claude "show me the ECS Fargate task definition schema" — it should
  fetch and return AWS documentation
- **aws-pricing**: Ask Claude "what is the price of an m5.large EC2 instance in us-east-1?"
  — it should return live pricing data
- **eks**: Ask Claude "list my EKS clusters in us-east-1" — it should call the EKS API
  and return cluster names
- **terraform**: Ask Claude "show me the AWS ECS Fargate Terraform module" — it should
  browse the Terraform registry and return module details

## Definition of done
- [ ] `claude mcp list` shows `aws-docs`, `aws-pricing`, `eks`, and `terraform` all as `connected`
- [ ] `aws sts get-caller-identity` returns a valid account ID (credentials working)
- [ ] Claude can answer "what is the price of an m5.large in us-east-1?" using aws-pricing MCP
- [ ] Claude can answer "search AWS docs for ECS task definition" using aws-docs MCP
- [ ] Claude can answer "list my EKS clusters" using eks MCP
- [ ] Claude can answer "show Terraform AWS ECS module" using terraform MCP
- [ ] `docs/mcp-setup.md` exists with current server list and verification steps
- [ ] `docs/iam-policy.json` exists with minimum required IAM permissions
- [ ] No AWS credentials or secrets are committed to git (`.env` and `~/.aws/` stay local)
