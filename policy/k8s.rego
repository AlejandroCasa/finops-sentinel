package main

# -----------------------------------------------------------------------------
# OPA / Rego Governance Policy for Kubernetes Manifests
# Zero-Trust DevSecOps & Container Hardening (AGENTS.md Gate 4)
# -----------------------------------------------------------------------------

# Rule 1: Deny Deployments that do not enforce runAsNonRoot: true
# (either at pod spec.template.spec.securityContext or container securityContext)
deny[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container_or_pod_run_as_non_root(input.spec.template.spec, container)
    msg := sprintf("Deployment '%v' container '%v' must enforce runAsNonRoot: true in securityContext", [input.metadata.name, container.name])
}

container_or_pod_run_as_non_root(pod_spec, container) {
    container.securityContext.runAsNonRoot == true
}

container_or_pod_run_as_non_root(pod_spec, container) {
    pod_spec.securityContext.runAsNonRoot == true
    not container.securityContext.runAsNonRoot == false
}

# Rule 2: Deny Deployments where containers do not enforce readOnlyRootFilesystem: true
deny[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container.securityContext.readOnlyRootFilesystem == true
    msg := sprintf("Deployment '%v' container '%v' must enforce readOnlyRootFilesystem: true in securityContext", [input.metadata.name, container.name])
}
