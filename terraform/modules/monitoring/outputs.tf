output "namespace" {
  description = "Namespace where the monitoring stack is installed"
  value       = helm_release.kube_prometheus_stack.namespace
}

output "release_name" {
  description = "Helm release name — child services are prefixed with this (e.g. kube-prometheus-stack-grafana)"
  value       = helm_release.kube_prometheus_stack.name
}
