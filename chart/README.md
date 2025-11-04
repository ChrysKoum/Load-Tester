# Hono Load Testing - Helm Chart

Deploy load tests against Eclipse Hono in Kubernetes using a simple, profile-based Helm chart.

## 🚀 Quick Start

```bash
# 1. Add your container registry (if using private images)
# Edit values.yaml and set image.repository

# 2. Install with default 'smoke' profile
helm install hono-test ./chart

# 3. Watch the test run
kubectl logs -f job/hono-test-loadgen

# 4. View results
kubectl logs job/hono-test-loadgen

# 5. Uninstall
helm uninstall hono-test
```

## 📋 Available Profiles

All profiles are defined in `config/hono.yaml`:

| Profile | Tenants | Total Devices | Protocols | Duration | Use Case |
|---------|---------|---------------|-----------|----------|----------|
| `smoke` | 1 | 1 | mqtt | 60s | Quick connectivity test |
| `standard` | 5 | 100 | mqtt, http | 600s | Standard load test |
| `stress` | 10 | 500 | mqtt, http | 1800s | Heavy stress test |

## 🎯 Usage Examples

### 1. Basic Smoke Test (Default)
```bash
helm install hono-test ./chart
```

### 2. Standard Load Test
```bash
helm install hono-test ./chart --set profile=standard
```

### 3. Stress Test
```bash
helm install hono-test ./chart --set profile=stress
```

### 4. Custom Test with Overrides
```bash
# Use standard profile but with only 50 devices and HTTP protocol
helm install hono-test ./chart \
  --set profile=standard \
  --set overrides.devices=50 \
  --set overrides.protocols=http
```

### 5. Disable Caching
```bash
# Create fresh tenants/devices every time
helm install hono-test ./chart --set cache.enabled=false
```

### 6. Clear Cache and Run
```bash
# Clear cached devices and create new ones
helm install hono-test ./chart --set cache.clear=true
```

### 7. Use Custom Config
```bash
# Deploy with your own hono.yaml
helm install hono-test ./chart --set-file config.honoYaml=./my-hono.yaml
```

## 📁 Output

- **Reports**: Stored in PVC `hono-test-reports` (access via pod or export)
- **Logs**: View with `kubectl logs job/hono-test-loadgen`
- **Cache**: Persisted in PVC `hono-test-cache`

### Accessing Reports

```bash
# Method 1: View from pod
kubectl exec -it job/hono-test-loadgen -- ls /app/reports

# Method 2: Copy to local machine
kubectl cp hono-test-loadgen-xxxxx:/app/reports ./reports

# Method 3: Mount PVC in a helper pod
kubectl run -it --rm debug --image=busybox \
  --overrides='{"spec":{"volumes":[{"name":"reports","persistentVolumeClaim":{"claimName":"hono-test-reports"}}],"containers":[{"name":"debug","image":"busybox","volumeMounts":[{"name":"reports","mountPath":"/reports"}]}]}}' \
  -- sh
```

## 🔧 Configuration

### values.yaml

```yaml
# Use predefined profile
profile: smoke

# Optional overrides
overrides:
  tenants: ""      # Override number of tenants
  devices: ""      # Override total number of devices  
  protocols: ""    # Override protocols
  messageInterval: ""
  duration: ""

# Caching
cache:
  enabled: true
  clear: false
  size: 500Mi

# Reports storage
reports:
  enabled: true
  size: 2Gi

# Image configuration
image:
  repository: yourrepo/hono-load-test
  tag: latest
```

### Custom Profiles

Edit `config/hono.yaml` in the chart directory:

```yaml
profiles:
  my-test:
    description: "My custom test"
    tenants: 3
    devices: 50          # Total devices
    protocols: [mqtt, http]
    message_interval: 5.0
    duration: 300
```

Then install:
```bash
helm install hono-test ./chart --set profile=my-test
```

## 🏗️ Architecture

The chart deploys 3 Kubernetes Jobs in sequence:

```
┌─────────────┐     ┌────────────┐     ┌──────────┐
│  registrar  │────▶│ validator  │────▶│ loadgen  │
│  (Job)      │     │  (Job)     │     │  (Job)   │
└─────────────┘     └────────────┘     └──────────┘
       │                                      │
       ▼                                      ▼
   [cache PVC]                          [reports PVC]
```

### Resource Requirements

Default resource limits:

- **registrar**: 500m CPU, 512Mi memory
- **validator**: 500m CPU, 512Mi memory  
- **loadgen**: 1000m CPU, 1Gi memory

Customize in `values.yaml`:

```yaml
loadgen:
  resources:
    limits:
      cpu: 2000m
      memory: 2Gi
    requests:
      cpu: 500m
      memory: 512Mi
```

## 📊 Monitoring

### View Logs

```bash
# All jobs
kubectl logs -l app.kubernetes.io/instance=hono-test

# Specific job
kubectl logs job/hono-test-registrar
kubectl logs job/hono-test-validator
kubectl logs job/hono-test-loadgen

# Follow logs
kubectl logs -f job/hono-test-loadgen
```

### Check Status

```bash
# Job status
kubectl get jobs -l app.kubernetes.io/instance=hono-test

# Pod status
kubectl get pods -l app.kubernetes.io/instance=hono-test

# Describe job
kubectl describe job hono-test-loadgen
```

## 🧹 Cleanup

```bash
# Uninstall release
helm uninstall hono-test

# Delete PVCs (optional - preserves cache and reports)
kubectl delete pvc hono-test-cache hono-test-reports hono-test-shared-data

# Complete cleanup
helm uninstall hono-test && \
kubectl delete pvc -l app.kubernetes.io/instance=hono-test
```

## 🆚 Comparison with Docker & Python

All three deployment methods use the **same config system** (`config/hono.yaml`):

### Python Script
```bash
python stress.py --profile smoke
python stress.py --profile standard --devices 50
```

### Docker Compose
```bash
PROFILE=smoke docker-compose up
PROFILE=standard DEVICES=50 docker-compose up
```

### Helm Chart (Kubernetes)
```bash
helm install test ./chart --set profile=smoke
helm install test ./chart --set profile=standard --set overrides.devices=50
```

**Same profiles, same behavior, same results!** ✅

## 🐛 Troubleshooting

### Job fails to start
```bash
# Check events
kubectl describe job hono-test-registrar

# Check pod logs
kubectl logs -l job-name=hono-test-registrar

# Check image pull
kubectl get events --sort-by='.lastTimestamp'
```

### Connection issues
```bash
# Test connectivity from pod
kubectl run -it --rm debug --image=busybox -- nslookup hono.eclipseprojects.io

# Check config
kubectl get configmap hono-test-config -o yaml
```

### Cache issues
```bash
# Delete cache PVC
kubectl delete pvc hono-test-cache

# Reinstall with cache cleared
helm upgrade --install hono-test ./chart --set cache.clear=true
```

### Out of resources
```bash
# Check resource usage
kubectl top pods -l app.kubernetes.io/instance=hono-test

# Reduce resource limits in values.yaml
```

## 📚 Advanced

### Multiple Tests in Parallel
```bash
# Run smoke test
helm install test-smoke ./chart --set profile=smoke

# Run standard test in parallel
helm install test-standard ./chart --set profile=standard

# Different namespaces
helm install test1 ./chart -n test1 --create-namespace
helm install test2 ./chart -n test2 --create-namespace
```

### Custom Image

```bash
# Build and push your image
docker build -t myregistry/hono-test:v1 .
docker push myregistry/hono-test:v1

# Install with custom image
helm install hono-test ./chart \
  --set image.repository=myregistry/hono-test \
  --set image.tag=v1
```

### Using with ArgoCD

```yaml
# application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: hono-load-test
spec:
  project: default
  source:
    repoURL: https://github.com/yourrepo/hono-load-test
    targetRevision: HEAD
    path: chart
    helm:
      values: |
        profile: standard
        overrides:
          devices: 100
  destination:
    server: https://kubernetes.default.svc
    namespace: load-testing
```

### Persistent Reports

To keep reports across test runs:

```yaml
# values.yaml
reports:
  enabled: true
  size: 10Gi  # Larger storage for multiple test runs
  storageClass: "standard"  # Use appropriate storage class
```

## 📖 Learn More

- Full configuration: See `config/hono.yaml`
- Minimal config: See `config/hono.min.example.yaml`
- Python script: See `../python-script/README.md`
- Docker Compose: See `../docker-compose/README.md`
- Values reference: See `values.yaml`
