
# Hono Load Test Suite

A modern, scalable, and multi-protocol framework for **stress-testing [Eclipse Hono](https://www.eclipse.org/hono/)** device ingestion using Python, Docker Compose, and Kubernetes (Helm).  
Easily simulate from a handful up to thousands of devices over MQTT, HTTP, CoAP, AMQP, and LoRa—locally, in CI, or at cloud scale.

---

## Table of Contents

- [Overview](#overview)
- [Feature Matrix](#feature-matrix)
- [Quick Start Guide](#quick-start-guide)
  - [Python Script](#python-script)
  - [Docker Compose](#docker-compose)
  - [Kubernetes/Helm (K3s, K8s)](#kuberneteshelm-k3s-k8s)
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
- Device registration (multi-tenant)
- Credential provisioning
- Telemetry & event validation
- Protocols: MQTT, HTTP, CoAP, AMQP, LoRa
- Parallel and/or distributed load generation
- Works with any Hono deployment (dev, staging, prod)

---

## Feature Matrix

| Feature                      | Python Script | Docker Compose | Kubernetes/Helm (K3s/K8s) |
|------------------------------|:------------:|:--------------:|:-------------------------:|
| Simulate 10–20 devices       |      ✅      |       ✅       |           ✅              |
| 100s–1000s of devices        |      ❌      |       ✅*      |           ✅              |
| Multi-protocol support       |      ✅      |       ✅       |           ✅              |
| Parallel device registration |      ⚠️      |       ✅       |           ✅              |
| Multi-tenancy                |      ✅      |       ✅       |           ✅              |
| Production-like scale        |      ❌      |       ⚠️      |           ✅              |
| Distributed/cloud execution  |      ❌      |       ⚠️      |           ✅              |
| Autoscaling                  |      ❌      |       ❌       |           ✅              |
| Local development            |      ✅      |       ✅       |           ✅              |
| CI/CD Integration            |      ⚠️      |       ✅       |           ✅              |

> *Docker Compose is suitable for moderate loads. For 1000+ simulated devices or full distributed/HA testing, use Kubernetes.

---

## Quick Start Guide

### Python Script

**Best for:**  
- Demos, debugging, small-scale (1–20 devices), or rapid prototyping

**How to run:**
```bash
cd python-script
pip install -r requirements.txt
cp ../docker-compose/hono.env.example hono.env  # Or use your own
python stress.py --mode 10fast --protocols mqtt http coap amqp lora --kind telemetry
```

* Configure modes, protocols, and telemetry/events as CLI options.
* Edit `hono.env` and `.env` to match your Hono deployment.

---

### Docker Compose

**Best for:**

* Local dev, simulating up to \~500 devices, and multi-protocol/multi-service testing

**How to run:**

```bash
cd docker-compose
cp .env.example .env
cp hono.env.example hono.env     # Or use your own values
docker compose build
docker compose up
```

* Edit `.env` and `hono.env` for device counts, tenants, intervals, and Hono endpoints.
* Logs from each service (registrar, validator, loadgen) are shown separately.

---

### Kubernetes/Helm (K3s, K8s)

**Best for:**

* Large-scale, cloud, CI/CD, or production-like distributed tests (1000+ devices)

**K3s is recommended for easy local Kubernetes clusters.**

**How to run:**

```bash
# 1. Install K3s (for local/dev)
curl -sfL https://get.k3s.io | sh -
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# 2. Build and push your Docker image to a registry
docker build -t yourrepo/hono-load-test:latest .
docker push yourrepo/hono-load-test:latest

# 3. Edit chart/values.yaml with your images and Hono endpoints

# 4. Install Helm if not present
curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash

# 5. Deploy with Helm
cd chart
helm install hono-load-test .

# 6. Observe pods and logs
kubectl get pods
kubectl logs deployment/hono-loadgen
```

* Scale up/down by editing `values.yaml` and running `helm upgrade`.
* Supports advanced use: multiple protocols, replica counts, resource limits, monitoring.

---

## Architecture

* **Registrar:** Registers tenants and devices, sets credentials.
* **Validator:** Validates device registration and first telemetry/event message (all protocols).
* **Loadgen:** Simulates device traffic (telemetry/events) over MQTT, HTTP, CoAP, AMQP, or LoRa.
* **Shared state** (device info) via volume or PVC.

Each component can be scaled or swapped out. Multi-protocol traffic can be run in parallel for realistic stress.

---

## When to Use Each Solution

| Use Case                       | Python Script | Docker Compose | Kubernetes/Helm (K3s) |
| ------------------------------ | :-----------: | :------------: | :-------------------: |
| Quick demo or local debug      |       ✅      |       ✅      |           ⚠️         |
| Moderate load, 100–500 devices |       ❌      |       ✅      |           ✅         |
| Full-scale (1,000+ devices)    |       ❌      |       ❌      |           ✅         |
| CI/CD pipeline                 |       ⚠️      |       ✅      |           ✅         |
| Production/prod-like test      |       ❌      |       ⚠️      |           ✅         |

**Legend:**
✅ = Recommended  ⚠️ = Usable/possible  ❌ = Not recommended

---

## Extending and Customizing

* Add or swap protocol loaders in `loadgen/`
* Tweak device/tenant counts and send rates in `.env`/`values.yaml`
* Add more telemetry fields/events to simulate realistic devices
* Add logging, Prometheus/Grafana monitoring, or custom metrics as needed

---

## Best Practices & Recommendations

* Start with Python or Compose for local/iterative development.
* Use K3s (or other K8s) for large, realistic, or CI-scale tests.
* Always validate Hono endpoints with a single device before scaling up.
* Tune `replicas` and `DEVICE_COUNT` gradually to avoid flooding your test or prod cluster.

---

## Troubleshooting

* **Connection errors:** Check your Hono endpoints and cluster/service network policies.
* **TLS issues:** Make sure to provide CA certs if your Hono instance uses custom or self-signed certs.
* **Resource exhaustion:** Monitor host/container CPU/RAM, especially with 100s+ devices.
* **Pods crashloop:** Check pod logs with `kubectl logs`.
* **Nothing received on Hono:** Validate device registration/credentials and protocol compatibility.

---

## License

Apache 2.0 or your preferred OSS license.

---

*Built for scalable, realistic, and protocol-agnostic IoT load testing with Eclipse Hono.*

---

*For further support or contributions, open an issue or pull request on GitHub.*