# Hono Load Testing - Complete Guide

Simple, profile-based load testing for Eclipse Hono with **identical configuration** across Python, Docker, and Kubernetes.

## 🎯 Quick Start (Choose Your Platform)

### Option 1: Python Script (Local)
```bash
cd python-script
pip install -r requirements.txt
python stress.py --profile smoke
```

### Option 2: Docker Compose
```bash
cd docker-compose
docker-compose up --build
```

### Option 3: Kubernetes (Helm)
```bash
helm install hono-test ./chart
```

**All three use the same `config/hono.yaml` file!** 🎉

## 📋 Available Profiles

| Profile | Tenants | Total Devices | Protocols | Duration | Use Case |
|---------|---------|---------------|-----------|----------|----------|
| `smoke` | 1 | 1 | mqtt | 60s | Quick connectivity test |
| `standard` | 5 | 100 | mqtt, http | 600s | Standard load test |
| `stress` | 10 | 500 | mqtt, http | 1800s | Heavy stress test |

## 🚀 Common Usage Patterns

### 1. Quick Smoke Test

**Python:**
```bash
python stress.py --profile smoke
# or just
python stress.py  # defaults to smoke
```

**Docker:**
```bash
docker-compose up
# or explicitly
PROFILE=smoke docker-compose up
```

**Kubernetes:**
```bash
helm install test ./chart
# or explicitly
helm install test ./chart --set profile=smoke
```

### 2. Standard Load Test

**Python:**
```bash
python stress.py --profile standard
```

**Docker:**
```bash
PROFILE=standard docker-compose up
```

**Kubernetes:**
```bash
helm install test ./chart --set profile=standard
```

### 3. Custom Override Examples

**Python:**
```bash
# Override devices and protocol
python stress.py --profile standard --devices 50 --protocols http

# Override duration
python stress.py --profile smoke --duration 120
```

**Docker:**
```bash
# Override devices and protocol
PROFILE=standard DEVICES=50 PROTOCOLS=http docker-compose up

# Multiple overrides
PROFILE=standard DEVICES=75 PROTOCOLS=mqtt,http MESSAGE_INTERVAL=5 docker-compose up
```

**Kubernetes:**
```bash
# Override devices and protocol
helm install test ./chart \
  --set profile=standard \
  --set overrides.devices=50 \
  --set overrides.protocols=http

# Multiple overrides
helm install test ./chart \
  --set profile=standard \
  --set overrides.devices=75 \
  --set overrides.protocols="mqtt,http" \
  --set overrides.messageInterval=5
```

## 📊 Feature Comparison

| Feature | Python | Docker | Kubernetes |
|---------|--------|--------|------------|
| **Profiles** | ✅ | ✅ | ✅ |
| **Caching** | ✅ | ✅ | ✅ |
| **Overrides** | ✅ | ✅ | ✅ |
| **Reports** | Local files | Host mount | PVC |
| **Logs** | Local files | Host mount | kubectl logs |
| **Best For** | Development | Testing | Production |

## 🔧 Configuration

### Single Source of Truth: `config/hono.yaml`

All three platforms use the same configuration file:

```yaml
# config/hono.yaml
profiles:
  smoke:
    description: "Quick test"
    tenants: 1
    devices: 1          # Total devices (distributed across tenants)
    protocols: [mqtt]
    message_interval: 30.0
    duration: 60
    
  standard:
    description: "Standard load"
    tenants: 5
    devices: 100        # Total devices across all tenants
    protocols: [mqtt, http]
    message_interval: 5.0
    duration: 600
```

### Creating Custom Profiles

1. Edit `config/hono.yaml`
2. Add your custom profile:

```yaml
profiles:
  my-test:
    description: "My custom test"
    tenants: 3
    devices: 50
    protocols: [mqtt, http]
    message_interval: 5.0
    duration: 300
```

3. Use it across all platforms:

```bash
# Python
python stress.py --profile my-test

# Docker
PROFILE=my-test docker-compose up

# Kubernetes
helm install test ./chart --set profile=my-test
```

## 💾 Caching

All platforms support device/tenant caching to avoid recreating infrastructure:

**Python:**
```bash
# Enable caching (default)
python stress.py --profile smoke

# Disable caching
python stress.py --profile smoke --no-cache

# Clear cache
python stress.py --profile smoke --clear-cache
```

**Docker:**
```bash
# Enable caching (default)
USE_CACHE=true docker-compose up

# Disable caching
USE_CACHE=false docker-compose up

# Clear cache
CLEAR_CACHE=true docker-compose up
```

**Kubernetes:**
```bash
# Enable caching (default)
helm install test ./chart --set cache.enabled=true

# Disable caching
helm install test ./chart --set cache.enabled=false

# Clear cache
helm install test ./chart --set cache.clear=true
```

## 📁 Output Locations

### Python Script
- Reports: `./reports/`
- Logs: `./logs/`
- Cache: `./cache/`

### Docker Compose
- Reports: `./reports/` (host mount)
- Logs: `./logs/` (host mount)
- Cache: Docker volume `cache_data`

### Kubernetes
- Reports: PVC `{release}-reports`
- Logs: `kubectl logs`
- Cache: PVC `{release}-cache`

## 🎓 Platform-Specific Details

### Python Script
- **Pros**: Fast iteration, easy debugging, local development
- **Cons**: Manual dependency management
- **See**: [python-script/README.md](python-script/README.md)

### Docker Compose
- **Pros**: Isolated environment, consistent dependencies, easy CI/CD
- **Cons**: Requires Docker
- **See**: [docker-compose/README.md](docker-compose/README.md)

### Kubernetes (Helm)
- **Pros**: Production-ready, scalable, resource management
- **Cons**: Requires Kubernetes cluster
- **See**: [chart/README.md](chart/README.md)

## 🔍 Monitoring & Debugging

### Python
```bash
# View live output
python stress.py --profile smoke

# Check logs
tail -f logs/stress_*.log

# View reports
ls -l reports/
```

### Docker
```bash
# View live logs
docker-compose logs -f loadgen

# Check all services
docker-compose logs

# Inspect volumes
docker volume inspect docker-compose_cache_data
```

### Kubernetes
```bash
# View job status
kubectl get jobs

# View logs
kubectl logs -f job/{release}-loadgen

# Check events
kubectl get events --sort-by='.lastTimestamp'

# Access reports
kubectl exec -it job/{release}-loadgen -- ls /app/reports
```

## 🧹 Cleanup

### Python
```bash
# Remove reports and logs
rm -rf reports/ logs/

# Clear cache
python stress.py --clear-cache
```

### Docker
```bash
# Stop services
docker-compose down

# Remove volumes (including cache)
docker-compose down -v

# Complete cleanup
docker-compose down -v --rmi all
```

### Kubernetes
```bash
# Uninstall release
helm uninstall test

# Remove PVCs
kubectl delete pvc test-cache test-reports test-shared-data

# Complete cleanup
helm uninstall test && kubectl delete pvc -l app.kubernetes.io/instance=test
```

## 🆘 Troubleshooting

### Connection Issues
All platforms: Check `config/hono.yaml` server endpoints match your Hono server

### Cache Issues
- Python: `python stress.py --clear-cache`
- Docker: `CLEAR_CACHE=true docker-compose up`
- Kubernetes: `helm upgrade test ./chart --set cache.clear=true`

### Resource Issues
- Python: Check system resources
- Docker: Increase Docker Desktop memory/CPU limits
- Kubernetes: Adjust resource limits in `values.yaml`

## 📚 Next Steps

1. **Start Simple**: Begin with the `smoke` profile on Python
2. **Customize**: Create your own profiles in `config/hono.yaml`
3. **Scale Up**: Move to Docker or Kubernetes for larger tests
4. **Production**: Use Kubernetes with proper resource limits

## 🔗 Quick Links

- Python Documentation: [python-script/README.md](python-script/README.md)
- Docker Documentation: [docker-compose/README.md](docker-compose/README.md)
- Kubernetes Documentation: [chart/README.md](chart/README.md)
- Configuration Guide: [CONFIG_IMPROVEMENT_PLAN.md](CONFIG_IMPROVEMENT_PLAN.md)
- Docker Migration: [DOCKER_MIGRATION_PLAN.md](DOCKER_MIGRATION_PLAN.md)

---

**Need help?** Check the platform-specific README files for detailed documentation.
