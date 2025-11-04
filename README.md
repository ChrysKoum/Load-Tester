
# Hono Load Test Suite

A modern, scalable, and multi-protocol framework for **stress-testing [Eclipse Hono](https://www.eclipse.org/hono/)** device ingestion using Python, Docker Compose, and Kubernetes (Helm).  
Easily simulate from a handful up to thousands of devices over MQTT, HTTP, CoAP, AMQP, and LoRa—locally, in CI, or at cloud scale.

**New in this version:** Profile-based configuration system with 3 predefined profiles (smoke, standard, stress) and device caching for efficient testing.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Test Profiles](#test-profiles)
- [Feature Matrix](#feature-matrix)
- [Quick Start Guide](#quick-start-guide)
  - [Python Script](#python-script)
  - [Docker Compose](#docker-compose)
  - [Kubernetes/Helm (K3s, K8s)](#kuberneteshelm-k3s-k8s)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [When to Use Each Solution](#when-to-use-each-solution)
- [Extending and Customizing](#extending-and-customizing)
- [Best Practices & Recommendations](#best-practices--recommendations)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

**Hono Load Test Suite** lets you rigorously test device registration, authentication, telemetry, and event publishing for Eclipse Hono installations.  
Choose the right tool for your scale: run a quick demo with a single Python file, orchestrate 100s of devices with Docker Compose, or simulate cloud-scale IoT traffic on Kubernetes—optimized for [K3s](https://k3s.io/) for effortless local clusters.

**Supports:**
- **Profile-based testing:** Choose from smoke, standard, or stress profiles—or create custom ones
- **Device caching:** Automatically reuses devices across test runs for faster iteration
- Device registration (multi-tenant)
- Credential provisioning
- Telemetry & event validation
- Protocols: MQTT, HTTP, CoAP, AMQP, LoRa
- Parallel and/or distributed load generation
- Works with any Hono deployment (dev, staging, prod)

---

## Key Features

### 🚀 Profile-Based Configuration
- **Smoke Profile:** 1 tenant, 1 device - Perfect for connectivity testing
- **Standard Profile:** 5 tenants, 100 devices - Moderate load testing
- **Stress Profile:** 10 tenants, 500 devices - High-load scenarios
- **Custom Profiles:** Create your own in `config/hono.yaml`

### 💾 Device Caching
- Automatically caches registered devices and tenants
- Reuses cached devices across test runs (80% validation threshold)
- Saves time by avoiding redundant device registration
- Cache keyed by server IP:port for multi-environment support

### 🔧 Flexible Configuration
- Unified YAML configuration across all platforms
- CLI/environment overrides for quick parameter changes
- Backward compatible with legacy test modes
- Easy customization without code changes

---

## Test Profiles

All three deployment methods (Python, Docker, Kubernetes) use the same profile system:

| Profile    | Tenants | Devices | Duration | Interval | Use Case                    |
|------------|---------|---------|----------|----------|----------------------------|
| **smoke**  | 1       | 1       | 60s      | 5s       | Connectivity & quick tests |
| **standard** | 5     | 100     | 300s     | 2s       | Moderate load testing      |
| **stress** | 10      | 500     | 600s     | 1s       | High-load scenarios        |

**Note:** The `devices` parameter represents the **total number of devices** distributed across all tenants, not devices per tenant.

---

## Feature Matrix

| Feature                      | Python Script | Docker Compose | Kubernetes/Helm (K3s/K8s) |
|------------------------------|:------------:|:--------------:|:-------------------------:|
| Profile-based testing        |      ✅      |       ✅       |           ✅              |
| Device caching               |      ✅      |       ✅       |           ✅              |
| Simulate 1–20 devices        |      ✅      |       ✅       |           ✅              |
| 100s–1000s of devices        |      ⚠️      |       ✅       |           ✅              |
| Multi-protocol support       |      ✅      |       ✅       |           ✅              |
| Parallel device registration |      ⚠️      |       ✅       |           ✅              |
| Multi-tenancy                |      ✅      |       ✅       |           ✅              |
| Production-like scale        |      ❌      |       ⚠️      |           ✅              |
| Distributed/cloud execution  |      ❌      |       ⚠️      |           ✅              |
| Autoscaling                  |      ❌      |       ❌       |           ✅              |
| Local development            |      ✅      |       ✅       |           ✅              |
| CI/CD Integration            |      ⚠️      |       ✅       |           ✅              |

> **Note:** Docker Compose is suitable for moderate loads (up to ~500 devices). For 1000+ simulated devices or full distributed/HA testing, use Kubernetes.

**Legend:** ✅ = Fully Supported  |  ⚠️ = Limited/Basic Support  |  ❌ = Not Supported

---

## Quick Start Guide

### Python Script

**Best for:**  
- Quick connectivity tests, debugging, and rapid prototyping
- Small-scale testing (1–100 devices)
- Local development

**Prerequisites:**
```bash
cd python-script
pip install -r requirements.txt
```

**Basic Usage (with profiles):**
```bash
# Run smoke test (default - 1 tenant, 1 device)
python stress.py

# Run standard profile (5 tenants, 100 devices)
python stress.py --profile standard

# Run stress profile (10 tenants, 500 devices)
python stress.py --profile stress

# List all available profiles
python stress.py --list-profiles

# Show details of a specific profile
python stress.py --show-profile standard
```

**Override profile settings:**
```bash
# Run smoke profile but with 5 devices and HTTP only
python stress.py --profile smoke --devices 5 --protocols http

# Run standard profile with custom duration
python stress.py --profile standard --duration 600
```

**Advanced options:**
```bash
# Disable device caching
python stress.py --profile smoke --no-cache

# Clear cache and run
python stress.py --profile standard --clear-cache

# Use custom config file
python stress.py --config my-custom-config.yaml --profile custom
```

**Configuration:**
- Edit `config/hono.yaml` for server settings and custom profiles
- Copy `config/hono.example.yaml` or `config/hono.min.example.yaml` as templates
- See `python-script/README.md` for detailed documentation

---

### Docker Compose

**Best for:**
- Multi-service orchestration
- Testing with moderate loads (up to ~500 devices)
- Isolated test environments

**Prerequisites:**
```bash
cd docker-compose
docker compose build
```

**Basic Usage (with profiles):**
```bash
# Run smoke test (default)
docker compose up

# Run with standard profile
PROFILE=standard docker compose up

# Run with stress profile
PROFILE=stress docker compose up
```

**Override profile settings:**
```bash
# Run smoke profile with 10 devices
PROFILE=smoke DEVICES=10 docker compose up

# Run standard profile with HTTP only
PROFILE=standard PROTOCOLS=http docker compose up

# Multiple overrides
PROFILE=standard DEVICES=200 TENANTS=10 DURATION=600 docker compose up
```

**Configuration:**
- Edit `docker-compose/.env` for Docker-specific settings
- Profiles defined in `config/hono.yaml` (same as Python script)
- See `docker-compose/README.md` for detailed documentation

---

### Kubernetes/Helm (K3s, K8s)

**Best for:**
- Large-scale testing (1000+ devices)
- Cloud-native deployments
- CI/CD pipelines
- Production-like distributed tests

**Prerequisites:**
```bash
# Install K3s (for local development)
curl -sfL https://get.k3s.io | sh -
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
```

**Basic Usage (with profiles):**
```bash
cd chart

# Deploy with smoke profile (default)
helm install hono-test .

# Deploy with standard profile
helm install hono-test . --set profile=standard

# Deploy with stress profile
helm install hono-test . --set profile=stress
```

**Override profile settings:**
```bash
# Run standard profile with custom device count
helm install hono-test . \
  --set profile=standard \
  --set overrides.devices=200

# Run with multiple overrides
helm install hono-test . \
  --set profile=stress \
  --set overrides.devices=1000 \
  --set overrides.tenants=20 \
  --set overrides.duration=1200

# Override protocols
helm install hono-test . \
  --set profile=standard \
  --set overrides.protocols="mqtt http"
```

**Monitoring:**
```bash
# Check pod status
kubectl get pods

# View logs
kubectl logs job/hono-registrar
kubectl logs job/hono-validator
kubectl logs job/hono-loadgen

# Check reports (if persistence enabled)
kubectl exec -it job/hono-loadgen -- ls /app/reports
```

**Configuration:**
- Edit `chart/values.yaml` for Kubernetes-specific settings
- Profiles defined in `chart/config/hono.yaml` (same as Python and Docker)
- See `chart/README.md` for detailed documentation

---

## Configuration

All three deployment methods share the same configuration system via `config/hono.yaml`:

```yaml
server:
  registry_host: "hono.eclipseprojects.io"
  registry_port: 28443
  mqtt_port: 8883
  http_port: 8443

cache:
  enabled: true
  directory: "./cache"
  validation_threshold: 0.8

profiles:
  smoke:
    tenants: 1
    devices: 1
    duration: 60
    interval: 5
    protocols: ["mqtt"]
    
  standard:
    tenants: 5
    devices: 100
    duration: 300
    interval: 2
    protocols: ["mqtt", "http"]
    
  stress:
    tenants: 10
    devices: 500
    duration: 600
    interval: 1
    protocols: ["mqtt", "http", "coap"]
```

**Creating custom profiles:**
1. Copy `config/hono.example.yaml` to `config/hono.yaml`
2. Add your custom profile under the `profiles:` section
3. Use it: `python stress.py --profile my-custom-profile`

For more details, see:
- `python-script/README.md` - Python script documentation
- `docker-compose/README.md` - Docker Compose documentation
- `chart/README.md` - Kubernetes/Helm documentation
- `GETTING_STARTED.md` - Unified guide for all platforms

---

## Architecture

The test suite consists of three main components that work together:

### Components

* **Registrar:** Registers tenants and devices with Hono, sets up credentials
  - Creates tenant IDs and device IDs
  - Provisions authentication credentials
  - Saves device information to cache for reuse

* **Validator:** Validates device registration and connectivity
  - Verifies devices can authenticate
  - Sends initial test messages across all protocols
  - Confirms Hono can receive data from devices

* **Loadgen:** Simulates realistic device traffic
  - Sends telemetry/event messages at configured intervals
  - Supports MQTT, HTTP, CoAP, AMQP, and LoRa protocols
  - Generates load according to profile settings

### Shared State

* **Device Cache:** JSON files stored in `./cache/` directory
  - Keyed by server IP:port for multi-environment support
  - Contains tenant IDs, device IDs, and credentials
  - Automatically reused across test runs (80% validation threshold)
  - Reduces test startup time by avoiding redundant registration

### Data Flow

```
1. Registrar creates tenants/devices → Cache
2. Validator reads cache → Tests connectivity → Hono
3. Loadgen reads cache → Sends telemetry/events → Hono
4. Results collected → Reports generated
```

Each component can be scaled independently in Docker Compose or Kubernetes deployments.

---

## When to Use Each Solution

| Use Case                       | Python Script | Docker Compose | Kubernetes/Helm (K3s) |
| ------------------------------ | :-----------: | :------------: | :-------------------: |
| Quick connectivity test        |       ✅      |       ⚠️      |           ❌         |
| Local debug & development      |       ✅      |       ✅      |           ⚠️         |
| Moderate load (100-500 devices)|       ⚠️      |       ✅      |           ✅         |
| Large-scale (1,000+ devices)   |       ❌      |       ⚠️      |           ✅         |
| Multi-protocol testing         |       ✅      |       ✅      |           ✅         |
| CI/CD pipeline                 |       ⚠️      |       ✅      |           ✅         |
| Production-like testing        |       ❌      |       ⚠️      |           ✅         |
| Distributed load generation    |       ❌      |       ❌      |           ✅         |

**Legend:**
- ✅ = **Recommended** - Best choice for this use case
- ⚠️ = **Usable** - Works but may have limitations
- ❌ = **Not Recommended** - Better alternatives available

### Decision Guide

**Choose Python Script when:**
- You need to quickly test connectivity with 1-10 devices
- Debugging configuration or protocol issues
- Running on a local development machine
- You want simple, direct execution without containers

**Choose Docker Compose when:**
- Testing with 10-500 devices
- Need isolated, reproducible test environments
- Want multi-service orchestration
- Running on a single host (local or remote)
- CI/CD with moderate scale requirements

**Choose Kubernetes/Helm when:**
- Testing with 500+ devices
- Need distributed load generation across multiple nodes
- Production-like environment testing
- Want autoscaling and resource management
- CI/CD with large-scale requirements
- Cloud or enterprise deployments

---

## Extending and Customizing

### Custom Test Profiles

Create custom profiles in `config/hono.yaml`:

```yaml
profiles:
  my-custom-profile:
    tenants: 3
    devices: 50
    duration: 180
    interval: 3
    protocols: ["mqtt", "http"]
    message_size: 256
    concurrent_connections: 20
```

Then use it:
```bash
# Python
python stress.py --profile my-custom-profile

# Docker Compose
PROFILE=my-custom-profile docker compose up

# Kubernetes
helm install test . --set profile=my-custom-profile
```

### Adding Custom Protocols

1. Implement protocol handler in `core/workers.py`
2. Add protocol configuration to `config/hono.yaml`
3. Update `models/config.py` with new protocol settings
4. Test with your custom profile

### Custom Telemetry/Event Data

Edit your profile in `config/hono.yaml`:

```yaml
profiles:
  custom-data:
    # ... other settings ...
    message_template:
      temperature: 25.5
      humidity: 60
      location:
        lat: 52.52
        lon: 13.405
```

### Monitoring and Metrics

Add custom monitoring:
- Prometheus metrics can be exposed via the reporting module
- Grafana dashboards for visualization
- Custom loggers in `utils/logger.py`
- Integration with APM tools (DataDog, New Relic, etc.)

### Environment-Specific Configs

Maintain separate config files for different environments:

```bash
config/
  hono-dev.yaml
  hono-staging.yaml
  hono-prod.yaml
```

Use them:
```bash
python stress.py --config config/hono-prod.yaml --profile stress
```

---

## Best Practices & Recommendations

### Testing Strategy

1. **Start Small:** Always begin with the `smoke` profile to verify connectivity
   ```bash
   python stress.py --profile smoke
   ```

2. **Gradual Scale-Up:** Progress through profiles: smoke → standard → stress
   ```bash
   python stress.py --profile standard
   python stress.py --profile stress
   ```

3. **Use Device Caching:** Let the cache system reuse devices to speed up testing
   - First run creates devices (slower)
   - Subsequent runs reuse devices (faster)
   - Clear cache only when testing device registration: `--clear-cache`

4. **Monitor Resources:** Watch CPU, memory, and network during tests
   - Python: Use `htop` or Task Manager
   - Docker: `docker stats`
   - Kubernetes: `kubectl top pods`

### Configuration Management

1. **Keep Environment-Specific Configs:** Maintain separate configs for dev/staging/prod
2. **Use Version Control:** Track `config/hono.yaml` changes in git
3. **Document Custom Profiles:** Add comments explaining custom profile purposes
4. **Test Config Changes:** Validate with smoke profile before running large tests

### Performance Optimization

1. **Adjust Intervals:** Lower intervals = higher load
   - Start with longer intervals (5s)
   - Gradually reduce based on Hono capacity

2. **Protocol Selection:** Different protocols have different overhead
   - MQTT: Most efficient for high-frequency telemetry
   - HTTP: Higher overhead but widely compatible
   - CoAP: Good for constrained environments

3. **Concurrent Connections:** Balance parallelism with resource limits
   ```yaml
   concurrent_connections: 50  # Adjust based on your system
   ```

4. **Message Size:** Larger messages increase network load
   ```yaml
   message_size: 128  # Start small, increase as needed
   ```

### Security

1. **Protect Credentials:** Never commit `hono.env` or configs with real credentials
2. **Use TLS:** Always enable TLS in production environments
3. **Rotate Test Credentials:** Change test passwords regularly
4. **Isolate Test Environments:** Use separate Hono instances for testing

### Troubleshooting Workflow

1. **Test connectivity first:** Use smoke profile
2. **Check Hono logs:** Verify Hono is receiving messages
3. **Examine cache:** Look at `./cache/*.json` for device info
4. **Review reports:** Check `./reports/` for detailed results
5. **Enable debug logging:** Set log level to DEBUG in config

### CI/CD Integration

**Docker Compose Example:**
```yaml
# .github/workflows/load-test.yml
- name: Run Load Test
  run: |
    cd docker-compose
    PROFILE=standard docker compose up --abort-on-container-exit
```

**Kubernetes Example:**
```yaml
# .github/workflows/k8s-load-test.yml
- name: Deploy Load Test
  run: |
    helm install load-test ./chart --set profile=standard --wait --timeout=10m
    kubectl logs job/hono-loadgen
```

---

## Troubleshooting

### Common Issues

#### Connection Refused / Timeout

**Symptoms:** Unable to connect to Hono server
```
ConnectionError: Cannot connect to hono.eclipseprojects.io:28443
```

**Solutions:**
1. Verify Hono server is running and accessible
2. Check firewall rules and network connectivity
3. Confirm ports in `config/hono.yaml` match your Hono deployment
4. Test with telnet: `telnet hono.eclipseprojects.io 28443`

#### Authentication Failed

**Symptoms:** Device registration or login fails
```
AuthenticationError: Failed to authenticate device
```

**Solutions:**
1. Check credentials in `config/hono.yaml`
2. Verify tenant and device exist in Hono registry
3. Clear cache and re-register: `--clear-cache`
4. Check Hono logs for authentication errors

#### Protocol Not Supported

**Symptoms:** Specific protocol fails while others work
```
ProtocolError: MQTT connection failed
```

**Solutions:**
1. Verify protocol is enabled in your Hono deployment
2. Check protocol-specific ports (MQTT: 8883, HTTP: 8443, etc.)
3. Test protocol individually: `--protocols mqtt`
4. Review Hono adapter logs for the failing protocol

#### Cache Issues

**Symptoms:** Cached devices fail validation
```
CacheWarning: Only 50% of cached devices valid, recreating...
```

**Solutions:**
1. This is normal if devices were deleted from Hono
2. Cache will automatically recreate devices below 80% threshold
3. Force recreation: `--clear-cache`
4. Check cache directory permissions: `./cache/`

#### Resource Exhaustion

**Symptoms:** High CPU/memory usage, slow performance
```
ResourceWarning: System resource limits reached
```

**Solutions:**
1. Reduce device count or increase interval
2. Use fewer concurrent connections
3. Monitor with: `docker stats` or `kubectl top pods`
4. Scale Kubernetes nodes if needed

#### Docker Compose Issues

**Symptoms:** Services fail to start or communicate
```
ERROR: Service 'registrar' failed to build
```

**Solutions:**
1. Rebuild images: `docker compose build --no-cache`
2. Check Docker logs: `docker compose logs registrar`
3. Verify volumes are mounted correctly
4. Ensure `config/hono.yaml` exists and is valid

#### Kubernetes Issues

**Symptoms:** Jobs don't complete or pods crash
```
Error: Job hono-registrar failed with BackoffLimitExceeded
```

**Solutions:**
1. Check pod logs: `kubectl logs job/hono-registrar`
2. Describe job: `kubectl describe job hono-registrar`
3. Verify ConfigMap is created: `kubectl get configmap hono-config`
4. Check PVC status: `kubectl get pvc`
5. Ensure sufficient cluster resources

### Debug Mode

Enable detailed logging for troubleshooting:

**Python:**
```bash
python stress.py --profile smoke --log-level DEBUG
```

**Docker Compose:**
```bash
LOG_LEVEL=DEBUG PROFILE=smoke docker compose up
```

**Kubernetes:**
```bash
helm install test . --set profile=smoke --set logging.level=DEBUG
```

### Getting Help

1. **Check Logs:** 
   - Python: `./logs/`
   - Docker: `docker compose logs`
   - Kubernetes: `kubectl logs`

2. **Review Reports:** Check `./reports/` for detailed test results

3. **Validate Configuration:** Use `--show-profile` to see effective config
   ```bash
   python stress.py --show-profile standard
   ```

4. **Test Components Individually:**
   - Registration: Run registrar only
   - Validation: Check validator output
   - Load generation: Monitor loadgen metrics

5. **Community Support:**
   - Eclipse Hono mailing list
   - GitHub issues
   - Hono Slack channel

### Known Limitations

- **Python Script:** Limited scalability beyond ~100 devices
- **Docker Compose:** Single-host limitation, not suitable for 1000+ devices
- **Cache:** 80% validation threshold may recreate devices frequently if Hono is unstable
- **Protocols:** Not all Hono deployments support all protocols (check your Hono configuration)

---

## License

Apache 2.0 or your preferred OSS license.

---

## Additional Resources

- **[GETTING_STARTED.md](./GETTING_STARTED.md)** - Unified quick-start guide for all platforms
- **[python-script/README.md](./python-script/README.md)** - Detailed Python script documentation
- **[docker-compose/README.md](./docker-compose/README.md)** - Docker Compose deployment guide
- **[chart/README.md](./chart/README.md)** - Kubernetes/Helm deployment guide
- **[Eclipse Hono Documentation](https://www.eclipse.org/hono/docs/)** - Official Hono documentation

---

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test your changes with all three deployment methods
4. Submit a pull request with clear description

---

## Changelog

### Version 2.0 (Current)
- ✅ Profile-based configuration system (smoke, standard, stress)
- ✅ Device caching for faster test iterations
- ✅ Unified YAML configuration across all platforms
- ✅ Improved documentation and examples
- ✅ Backward compatibility with legacy test modes

### Version 1.0
- Initial release with Python script
- Docker Compose support
- Kubernetes/Helm charts
- Multi-protocol support (MQTT, HTTP, CoAP, AMQP, LoRa)

---

*Built for scalable, realistic, and protocol-agnostic IoT load testing with Eclipse Hono.*

---

**Quick Links:**
- 🚀 [Quick Start](#quick-start-guide)
- 📊 [Test Profiles](#test-profiles)
- 🔧 [Configuration](#configuration)
- 🏗️ [Architecture](#architecture)
- 🤝 [Contributing](#contributing)