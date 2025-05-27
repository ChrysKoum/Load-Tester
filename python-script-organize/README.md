# Hono Load Test Suite - Refactored Modular Architecture

This document describes the refactored modular architecture of the Hono Load Test Suite, which improves maintainability, readability, and code organization while preserving all existing functionality.

## 📁 Project Structure

```
python-script/
├── stress.py                     # Original monolithic file (preserved)
├── stress_refactored.py          # New main entry point
├── requirements.txt              # Dependencies
├── README.md                     # This documentation
├── config/                       # Configuration modules
│   ├── __init__.py
│   └── hono_config.py            # HonoConfig dataclass and env loading
├── models/                       # Data models
│   ├── __init__.py
│   └── device.py                 # Device dataclass
├── core/                        # Core business logic
│   ├── __init__.py
│   ├── load_tester.py           # Main HonoLoadTester orchestrator
│   ├── infrastructure.py       # Tenant/device creation & validation
│   ├── workers.py               # Protocol workers (MQTT, HTTP, etc.)
│   └── reporting.py             # Statistics & report generation
└── utils/                       # Utilities and constants
    ├── __init__.py
    └── constants.py             # Library availability checks
```

## 🔧 Module Responsibilities

### 📋 Configuration (`config/`)
- **`hono_config.py`**: Contains the `HonoConfig` dataclass and environment loading functionality
- Handles all endpoint configurations, TLS settings, and client options
- Provides async `load_config_from_env()` function

### 🗂️ Models (`models/`)
- **`device.py`**: Contains the `Device` dataclass
- Represents a device in the load test with ID, tenant, credentials

### 🏗️ Core Logic (`core/`)
- **`load_tester.py`**: Main orchestrator class `HonoLoadTester`
- **`infrastructure.py`**: `InfrastructureManager` for tenant/device setup and validation
- **`workers.py`**: `ProtocolWorkers` containing MQTT and HTTP worker functions
- **`reporting.py`**: `ReportingManager` for statistics collection and report generation

### 🛠️ Utilities (`utils/`)
- **`constants.py`**: Library availability checks and constants
- Checks for matplotlib, pandas, CoAP, AMQP library availability

## 🚀 Usage

### Basic Usage
The refactored version maintains the same command-line interface:

```bash
# Run with default settings (10 devices, MQTT, 5.75s interval)
python stress_refactored.py

# Run tiny test (2 tenants, 2 devices)
python stress_refactored.py --tiny

# Run with custom settings
python stress_refactored.py --mode custom --devices 50 --interval 30 --protocols mqtt http

# Generate detailed reports
python stress_refactored.py --report --report-dir ./my-reports
```

### Import and Use Programmatically
```python
from config.hono_config import HonoConfig
from core.load_tester import HonoLoadTester

# Create configuration
config = HonoConfig()
config.registry_ip = "my-hono-registry.example.com"

# Initialize tester
tester = HonoLoadTester(config)

# Load environment configuration
await tester.load_config_from_env("my-hono.env")

# Setup infrastructure
success = await tester.setup_infrastructure(num_tenants=3, num_devices=15)

# Run load test
if success:
    tester.start_load_test(["mqtt", "http"], message_interval=10.0)
```

## ✨ Benefits of Refactoring

### 🎯 **Separation of Concerns**
- Configuration management isolated in `config/`
- Data models separated in `models/`
- Business logic split into focused modules in `core/`
- Utilities and constants centralized in `utils/`

### 🧩 **Modularity**
- Each module has a single, well-defined responsibility
- Easy to test individual components
- Simple to extend with new protocols or features

### 📖 **Readability**
- Clear module structure makes codebase navigation intuitive
- Reduced file size makes individual modules easier to understand
- Better documentation and type hints

### 🔧 **Maintainability**
- Changes to specific functionality are isolated to relevant modules
- Easier to debug issues in specific areas
- Simple to add new features without affecting existing code

### 🧪 **Testability**
- Individual modules can be unit tested independently
- Mock objects can be easily injected for testing
- Clear interfaces between modules

## 🔄 Migration from Original

The original `stress.py` file is preserved and fully functional. The refactored version maintains:

- ✅ **100% API Compatibility**: Same command-line arguments and behavior
- ✅ **Same Functionality**: All features work identically
- ✅ **Same Performance**: No performance degradation
- ✅ **Same Dependencies**: Uses the same requirements.txt

## 🧪 Testing the Refactored Version

```bash
# Syntax check all modules
python -m py_compile stress_refactored.py
python -m py_compile config/hono_config.py
python -m py_compile models/device.py
python -m py_compile core/load_tester.py
python -m py_compile core/infrastructure.py
python -m py_compile core/workers.py
python -m py_compile core/reporting.py
python -m py_compile utils/constants.py

# Run a quick test
python stress_refactored.py --tiny --setup-only
```

## 📈 Future Enhancements

The modular structure makes it easy to add:

1. **New Protocols**: Add CoAP, AMQP, LoRa workers in `core/workers.py`
2. **Enhanced Reporting**: Extend `core/reporting.py` with new chart types
3. **Configuration Sources**: Add database or API config sources to `config/`
4. **Data Models**: Add more complex device types in `models/`
5. **Monitoring**: Add real-time dashboard in a new `monitoring/` module

## 🎯 Best Practices Followed

- **Single Responsibility Principle**: Each module has one clear purpose
- **Dependency Injection**: Configuration and dependencies passed explicitly
- **Type Hints**: Full type annotations for better IDE support
- **Async/Await**: Proper async programming patterns
- **Error Handling**: Comprehensive exception handling
- **Logging**: Structured logging throughout
- **Documentation**: Clear docstrings and comments
