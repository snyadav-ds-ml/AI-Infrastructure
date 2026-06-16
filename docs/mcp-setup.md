# MCP Setup Reference

This document describes the MCP (Model Context Protocol) servers configured for this project
so Claude Code can assist with AWS, EKS, and Terraform operations directly.

## Prerequisites

| Tool | Required Version | Install |
|---|---|---|
| `uv` / `uvx` | any | `brew install uv` |
| `npx` | ≥ 18 | ships with Node.js |
| `aws` CLI | any | `brew install awscli` |
| AWS credentials | — | `aws configure` |

## MCP Servers

Servers are registered via `claude mcp add` and stored in `~/.claude.json` keyed by project
path. Do **not** edit `settings.json` for MCP registration — Claude Code does not read MCP
servers from that file.

| Name | Command | Purpose |
|---|---|---|
| `aws-docs` | `uvx awslabs.aws-documentation-mcp-server@latest` | Search and read AWS documentation inline |
| `aws-pricing` | `uvx awslabs.aws-pricing-mcp-server@latest` | Query live AWS service pricing and cost estimates |
| `eks` | `uvx awslabs.eks-mcp-server@latest` | Manage EKS clusters — nodes, pods, deployments, logs |
| `terraform` | `npx -y terraform-mcp-server` | Browse Terraform registry — providers, modules, resource docs |

All servers run as local child processes started by Claude Code — nothing is deployed remotely.
AWS servers pick up credentials from `~/.aws/credentials` automatically.

### Registration commands

```bash
claude mcp add aws-docs \
  -e FASTMCP_LOG_LEVEL=ERROR \
  -- uvx awslabs.aws-documentation-mcp-server@latest

claude mcp add aws-pricing \
  -e FASTMCP_LOG_LEVEL=ERROR \
  -e AWS_REGION=us-east-1 \
  -- uvx awslabs.aws-pricing-mcp-server@latest

claude mcp add eks \
  -e FASTMCP_LOG_LEVEL=ERROR \
  -e AWS_REGION=us-east-1 \
  -- uvx awslabs.eks-mcp-server@latest

claude mcp add terraform \
  -- npx -y terraform-mcp-server
```

> **Yanked packages (do not use):**
> - `awslabs.core-mcp-server` — yanked; replaced by individual servers
> - `awslabs.cdk-mcp-server` — yanked; superseded by `awslabs.aws-iac-mcp-server`

## Verify Setup

1. Run `claude mcp list` — all four servers should show `✓ Connected`.
2. Run the following CLI check:

```bash
aws sts get-caller-identity
```

3. Test each server in a new Claude Code session:
   - *"Search AWS docs for ECS task definition"* → uses `aws-docs`
   - *"What is the price of an m5.large in us-east-1?"* → uses `aws-pricing`
   - *"List my EKS clusters in us-east-1"* → uses `eks`
   - *"Show me the AWS ECS Fargate Terraform module"* → uses `terraform`

## IAM Permissions

The AWS credentials must cover the services called by `aws-pricing` and `eks`. See
`docs/iam-policy.json` for the full policy. Key actions required:

- **Pricing** — `pricing:GetProducts`, `pricing:DescribeServices`
- **Cost Explorer** — `ce:GetCostAndUsage`, `ce:GetCostForecast`
- **EKS** — `eks:ListClusters`, `eks:DescribeCluster`, `eks:ListNodegroups`, `eks:AccessKubernetesApi`
- **STS** — `sts:GetCallerIdentity`

To apply the policy to an IAM user:

```bash
aws iam put-user-policy \
  --user-name <your-iam-user> \
  --policy-name ml-infra-mcp-policy \
  --policy-document file://docs/iam-policy.json
```

## Troubleshooting

**Server shows `failed` in `claude mcp list`:**
- Run the `uvx` or `npx` command directly in a terminal to see the raw error output.
- For AWS servers: confirm `aws sts get-caller-identity` succeeds first.

**AWS calls fail with `AccessDenied`:**
- Check that the IAM user has the policy in `docs/iam-policy.json` attached.
- Run `aws sts get-caller-identity` to confirm the correct account/user is active.

**`uv` not found:**
- Run `brew install uv` then open a new terminal session.

**EKS server can't find cluster:**
- Confirm the cluster exists: `aws eks list-clusters --region us-east-1`
- Ensure the IAM user has `eks:ListClusters` permission.
