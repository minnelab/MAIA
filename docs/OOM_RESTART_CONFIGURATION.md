# OOM Pod Restart Configuration

This document describes the changes made to enable automatic restart of pods that terminate due to Out Of Memory (OOM) errors in the MAIA platform.

## Overview

Previously, when pods running in MAIA (via JupyterHub or as Jobs) encountered OOM errors, they would not automatically restart, requiring manual intervention. This update configures the platform to automatically restart failed pods, improving reliability for interactive and batch workloads.

## Changes Made

### 1. JupyterHub Singleuser Pods

**File:** `MAIA_scripts/MAIA_create_JupyterHub_config.py`

**Change:** Added `extraPodConfig` with `restartPolicy: OnFailure` to the JupyterHub singleuser configuration.

```python
"singleuser": {
    ...
    "extraPodConfig": {
        "restartPolicy": "OnFailure",
    },
    ...
}
```

**Impact:** All JupyterHub notebook pods will now automatically restart when they fail due to OOM or other errors. The pod will be restarted by Kubernetes, preserving the user's persistent storage.

### 2. MAIAKubeGate Jobs

**Files:** 
- `charts/maiakubegate/templates/job.yaml`
- `charts/maiakubegate/values.yaml`

**Changes:**
- Made `restartPolicy` configurable with default value `OnFailure`
- Made `backoffLimit` configurable with default value `3`

**Default Configuration:**
```yaml
restartPolicy: OnFailure
backoffLimit: 3
```

**Impact:** User workload Jobs submitted via MAIAKubeGate will automatically retry up to 3 times on failure, including OOM errors. This behavior can be customized by setting `restartPolicy` and `backoffLimit` in the Helm values.

**Example - Disable retries:**
```yaml
restartPolicy: Never
backoffLimit: 0
```

**Example - Increase retries:**
```yaml
restartPolicy: OnFailure
backoffLimit: 6
```

### 3. MAIAKubeGate Kaniko Build Jobs

**Files:**
- `charts/maiakubegate-kaniko/templates/job.yaml`
- `charts/maiakubegate-kaniko/values.yaml`

**Changes:**
- Made `restartPolicy` configurable with default value `Never`
- Made `backoffLimit` configurable with default value `0`

**Default Configuration:**
```yaml
restartPolicy: Never
backoffLimit: 0
```

**Impact:** Kaniko build jobs maintain their original behavior (no automatic retries) as build failures typically require code/configuration changes rather than simple retries. This behavior can be customized if needed by setting the values in the Helm chart.

## Kubernetes Restart Policy Behavior

### For Pods (JupyterHub)

- **OnFailure**: Container is restarted only if it exits with a non-zero exit code (including OOM). The pod remains scheduled on the same node.
- **Always**: Container is restarted regardless of exit code (not used in this configuration).
- **Never**: Container is never restarted (original problematic behavior).

### For Jobs

The `restartPolicy` combined with `backoffLimit` determines retry behavior:

- **restartPolicy: OnFailure**: Failed containers are restarted within the same pod
- **backoffLimit**: Maximum number of pod failures before the job is marked as failed
- When a container exits with OOM, it's considered a failure and will be retried according to these policies

## Testing

To verify the configuration:

1. **JupyterHub pods:** Launch a notebook and trigger an OOM error. The pod should automatically restart.
2. **MAIAKubeGate jobs:** Submit a job that will OOM. It should retry up to 3 times (by default).

### Helm Template Validation

You can validate the rendered templates:

```bash
# Check maiakubegate Job configuration
cd charts/maiakubegate
helm template test . --set allocatedTime=3600 | grep -A 5 "restartPolicy"

# Check with custom values
helm template test . --set allocatedTime=3600 --set backoffLimit=6 | grep "backoffLimit"
```

## Migration Notes

### Existing Deployments

For existing MAIA deployments:

1. **JupyterHub:** The next time the JupyterHub configuration is regenerated using `MAIA_create_JupyterHub_config.py`, the new restart policy will be applied. Existing running pods will continue with their current configuration until restarted.

2. **Jobs:** New jobs will use the new defaults. Existing job definitions can be updated by modifying their Helm values.

### Backward Compatibility

The changes are backward compatible:
- JupyterHub: The `extraPodConfig` is additive and doesn't conflict with existing configuration
- Jobs: The defaults are set using the `{{ .Values.setting | default "value" }}` pattern, so existing deployments without these values will use the new defaults

## Related Resources

- [Kubernetes Pod Lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
- [Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [JupyterHub KubeSpawner Configuration](https://jupyterhub-kubespawner.readthedocs.io/)

## Future Considerations

1. **Memory Limits:** Consider implementing or documenting memory limit best practices to prevent OOM in the first place
2. **Monitoring:** Add monitoring/alerting for OOM events to help users understand when their workloads need more resources
3. **Kubeflow Integration:** If MAIA manages Kubeflow deployments in the future, similar restart policies should be applied
