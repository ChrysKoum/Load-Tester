# Hono Load Test - Python Script

A comprehensive Python-based load testing tool for Eclipse Hono with multi-protocol support.

## Features

- **Multi-tenant setup**: Automatically creates and manages multiple tenants
- **Device provisioning**: Registers devices and sets up authentication credentials
- **Protocol support**: MQTT, HTTP (with extensibility for CoAP, AMQP, LoRa)
- **Validation**: Tests device connectivity before starting load tests
- **Flexible test scenarios**: Pre-configured and custom test modes
- **Real-time monitoring**: Live statistics during test execution

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Hono endpoints**:
   ```bash
   # Copy the example and edit with your Hono instance details
   cp ../docker-compose/hono.env.example hono.env
   # Edit hono.env with your actual Hono endpoints
   ```

3. **Run a quick test** (10 devices, 5.75s interval):
   ```bash
   python stress.py --mode 10fast --protocols mqtt
   ```

4. **Run a sustained test** (100 devices, 60s interval):
   ```bash
   python stress.py --mode 100slow --protocols mqtt http
   ```

## Test Modes

### Predefined Modes

- **`10fast`**: 10 devices sending telemetry every ~5.75 seconds
- **`100slow`**: 100 devices sending telemetry every 60 seconds
- **`custom`**: Use custom parameters with `--devices` and `--interval`

### Custom Configuration

```bash
# Custom test with specific parameters
python stress.py --mode custom --devices 50 --interval 30 --protocols mqtt http --kind event
```

## Command Line Options

```
usage: stress.py [-h] [--mode {10fast,100slow,custom}] [--protocols {mqtt,http,coap,amqp,lora} [{mqtt,http,coap,amqp,lora} ...]]
                 [--kind {telemetry,event}] [--tenants TENANTS] [--devices DEVICES] [--interval INTERVAL] [--env-file ENV_FILE]
                 [--setup-only]

Hono Load Test Suite

optional arguments:
  -h, --help            show this help message and exit
  --mode {10fast,100slow,custom}
                        Test mode: 10fast (10 devices, 5.75s interval), 100slow (100 devices, 60s interval), or custom
  --protocols {mqtt,http,coap,amqp,lora} [{mqtt,http,coap,amqp,lora} ...]
                        Protocols to use for testing
  --kind {telemetry,event}
                        Type of messages to send
  --tenants TENANTS     Number of tenants to create
  --devices DEVICES     Number of devices to create (overrides mode)
  --interval INTERVAL   Message interval in seconds (overrides mode)
  --env-file ENV_FILE   Environment file to load
  --setup-only          Only setup infrastructure, don't run load test
```

## Configuration File (hono.env)

The script loads configuration from a `hono.env` file. Example format:

```bash
export REGISTRY_IP=hono.eclipseprojects.io
export HTTP_ADAPTER_IP=hono.eclipseprojects.io
export MQTT_ADAPTER_IP=hono.eclipseprojects.io
export COAP_ADAPTER_IP=hono.eclipseprojects.io
export AMQP_ADAPTER_IP=hono.eclipseprojects.io
export LORA_ADAPTER_IP=hono.eclipseprojects.io
```

## Test Execution Flow

1. **Infrastructure Setup**:
   - Creates specified number of tenants (default: 5)
   - Distributes devices evenly across tenants
   - Sets random passwords for each device
   - Validates connectivity with initial HTTP telemetry

2. **Validation Phase**:
   - Sends test telemetry message from each device
   - Verifies 2xx HTTP status responses
   - Reports validation success/failure counts

3. **Load Testing Phase**:
   - Waits for user confirmation to start
   - Distributes devices across specified protocols
   - Sends telemetry/event messages at configured intervals
   - Provides real-time statistics

4. **Monitoring**:
   - Live statistics every 10 seconds
   - Final summary with success rates

## Example Usage

### Basic MQTT Load Test
```bash
python stress.py --mode 10fast --protocols mqtt --kind telemetry
```

### Multi-Protocol Test
```bash
python stress.py --mode custom --devices 20 --interval 15 --protocols mqtt http --kind event
```

### Setup Only (No Load Test)
```bash
python stress.py --setup-only --tenants 3 --devices 15
```

### Large Scale Test
```bash
python stress.py --mode 100slow --protocols mqtt --kind telemetry --tenants 10
```

## Troubleshooting

### Connection Issues
- Verify Hono endpoints in `hono.env`
- Check network connectivity to Hono instance
- Ensure proper firewall/security group settings

### TLS/SSL Issues
- Set `verify_ssl: False` in configuration for self-signed certificates
- Provide CA certificate file path if using custom CA

### Authentication Errors
- Verify device registration was successful
- Check tenant and device IDs in logs
- Ensure password complexity meets Hono requirements

### Performance Issues
- Reduce number of concurrent devices for resource-constrained systems
- Increase message intervals to reduce load
- Monitor system resources (CPU, memory, network)

## Output Example

```
2025-05-26 14:30:15 - __main__ - INFO - Loaded configuration: Registry=hono.eclipseprojects.io
2025-05-26 14:30:15 - __main__ - INFO - Setting up 5 tenants with 10 devices total...
2025-05-26 14:30:16 - __main__ - INFO - Created tenant: a1b2c3d4-e5f6-7890-abcd-ef1234567890
2025-05-26 14:30:17 - __main__ - INFO - Created 5 tenants successfully
2025-05-26 14:30:20 - __main__ - INFO - Created 10 devices successfully
2025-05-26 14:30:22 - __main__ - INFO - Validation complete: 10/10 devices validated
2025-05-26 14:30:22 - __main__ - INFO - ✅ All devices validated successfully! Ready to start load testing.

🚀 Starting load test: 10 devices, 5.75s interval
Protocols: ['mqtt'], Message type: telemetry
Press Enter when ready to start...

2025-05-26 14:30:35 - __main__ - INFO - Starting load test with 10 devices using protocols: ['mqtt']
2025-05-26 14:30:45 - __main__ - INFO - Stats - Sent: 17, Failed: 0, Rate: 1.7 msg/s

Press Enter to stop the load test...

==================================================
FINAL LOAD TEST STATISTICS
==================================================
Tenants registered: 5
Devices registered: 10
Devices validated: 10
Validation failures: 0
Messages sent: 156
Messages failed: 0
Success rate: 100.0%
==================================================
```

## Protocol Support Status

- ✅ **MQTT**: Fully implemented with QoS support
- ✅ **HTTP**: Fully implemented with authentication
- 🚧 **CoAP**: Planned (requires additional dependencies)
- 🚧 **AMQP**: Planned (requires additional dependencies)
- 🚧 **LoRa**: Planned (requires additional dependencies)

## Dependencies

- `aiohttp`: Async HTTP client for REST API calls
- `paho-mqtt`: MQTT client library
- Standard Python libraries (asyncio, json, logging, etc.)

## Notes

- The script automatically handles device distribution across tenants
- SSL verification is disabled by default for testing environments
- All timestamps are in Unix epoch format
- Device passwords are randomly generated UUIDs
- Test data includes realistic sensor values (temperature, humidity, pressure)
