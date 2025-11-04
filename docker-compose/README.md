# Hono Load Testing - Docker Compose

Run load tests against Eclipse Hono using Docker Compose with a simple, profile-based configuration.

## 🚀 Quick Start

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Edit .env to set your profile (optional, defaults to 'smoke')
# PROFILE=smoke

# 3. Run the test
docker-compose up --build

# 4. Stop the test
docker-compose down
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
docker-compose up
```

### 2. Standard Load Test
```bash
PROFILE=standard docker-compose up
```

### 3. Stress Test
```bash
PROFILE=stress docker-compose up
```

### 4. Custom Test with Overrides
```bash
# Use standard profile but with only 50 devices and HTTP protocol
PROFILE=standard DEVICES=50 PROTOCOLS=http docker-compose up
```

### 5. Disable Caching
```bash
# Create fresh tenants/devices every time
USE_CACHE=false docker-compose up
```

### 6. Clear Cache and Run
```bash
# Clear cached devices and create new ones
CLEAR_CACHE=true docker-compose up
```

## 📁 Output

- **Reports**: Saved to `./reports/` directory
- **Logs**: Saved to `./logs/` directory  
- **Cache**: Stored in Docker volume `cache_data`

## 🔧 Configuration

### Profile-Based (Recommended)
Edit `config/hono.yaml` to:
- Modify existing profiles
- Add custom profiles
- Change server endpoints

Example custom profile:
```yaml
profiles:
  my-test:
    description: "My custom test"
    tenants: 3
    devices: 50          # Total devices distributed across tenants
    protocols: [mqtt, http]
    message_interval: 5.0
    duration: 300
```

Then run:
```bash
PROFILE=my-test docker-compose up
```

### Environment Variables (Override)
Set in `.env` file or command line:

```bash
# .env file
PROFILE=standard
DEVICES=75
PROTOCOLS=mqtt,http
MESSAGE_INTERVAL=3
DURATION=900
USE_CACHE=true
```

## 🏗️ Architecture

The Docker Compose setup runs 3 services in sequence:

1. **registrar** - Creates tenants and devices (with caching)
2. **validator** - Validates devices can communicate
3. **loadgen** - Generates load on validated devices

```
┌─────────────┐     ┌────────────┐     ┌──────────┐
│  registrar  │────▶│ validator  │────▶│ loadgen  │
│ (creates)   │     │ (validates)│     │  (tests) │
└─────────────┘     └────────────┘     └──────────┘
       │                                      │
       ▼                                      ▼
  [cache_data]                          [reports/]
```

## 📊 Monitoring

View live logs:
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f loadgen

# Last 100 lines
docker-compose logs --tail=100 loadgen
```

## 🧹 Cleanup

```bash
# Stop services
docker-compose down

# Stop and remove volumes (including cache)
docker-compose down -v

# Remove everything including images
docker-compose down -v --rmi all
```

## 🆚 Docker vs Python Script

Both use the **same config system** (`config/hono.yaml`):

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

**Same profiles, same behavior, same results!** ✅

## 🐛 Troubleshooting

### Service fails to start
```bash
# Check logs
docker-compose logs registrar

# Rebuild from scratch
docker-compose build --no-cache
docker-compose up
```

### Cache issues
```bash
# Clear cache
CLEAR_CACHE=true docker-compose up registrar

# Or manually remove volume
docker-compose down -v
```

### Connection issues
1. Check `config/hono.yaml` server endpoints
2. Verify network connectivity: `docker-compose exec loadgen ping hono.eclipseprojects.io`
3. Check TLS settings in config

### Permission issues
```bash
# Fix permissions on output directories
chmod -R 777 reports/ logs/
```

## 📚 Advanced

### Run specific service only
```bash
# Only create infrastructure
docker-compose up registrar

# Only validate (requires registrar first)
docker-compose up registrar validator

# Full test
docker-compose up registrar validator loadgen
```

### Scale load generators
```bash
# Run multiple load generators (not recommended with current setup)
docker-compose up --scale loadgen=3
```

### Custom config file
```bash
# Use different config
docker-compose run -e CONFIG_FILE=/app/config/my-config.yaml loadgen
```

## 🎓 Learn More

- Full configuration options: See `config/hono.yaml`
- Minimal config example: See `config/hono.min.example.yaml`
- Python script usage: See `../python-script/README.md`
- Docker migration plan: See `../DOCKER_MIGRATION_PLAN.md`
