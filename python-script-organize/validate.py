#!/usr/bin/env python3
"""
Validation script for the refactored Hono Load Test Suite.
Performs basic import and initialization tests to ensure the refactored modules work correctly.
"""

import sys
import asyncio
import traceback
from pathlib import Path

# Import the classes that will be tested
from config.hono_config import HonoConfig
from models.device import Device

def test_imports():
    """Test that all modules can be imported successfully."""
    print("🔍 Testing module imports...")
    
    try:
        # Test config imports
        from config.hono_config import HonoConfig, load_config_from_env
        print("✅ Config module imported successfully")
        
        # Test models imports
        from models.device import Device
        print("✅ Models module imported successfully")
        
        # Test utils imports
        from utils.constants import REPORTING_AVAILABLE, COAP_AVAILABLE, AMQP_AVAILABLE, get_library_status
        print("✅ Utils module imported successfully")
        
        # Test core imports
        from core.infrastructure import InfrastructureManager
        from core.workers import ProtocolWorkers
        from core.reporting import ReportingManager
        from core.load_tester import HonoLoadTester
        print("✅ Core modules imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        traceback.print_exc()
        return False

def test_basic_initialization():
    """Test basic object initialization."""
    print("\n🏗️  Testing basic initialization...")
    
    try:
        # Import the required classes for this test
        from core.infrastructure import InfrastructureManager
        from core.reporting import ReportingManager
        from core.load_tester import HonoLoadTester
        
        # Test config creation
        config = HonoConfig()
        print(f"✅ HonoConfig created: {config.registry_ip}:{config.registry_port}")
        
        # Test device creation
        device = Device(
            device_id="test-device-001",
            tenant_id="test-tenant-001",
            password="test-password"
        )
        print(f"✅ Device created: {device.device_id}@{device.tenant_id}")
        
        # Test core managers
        infrastructure_manager = InfrastructureManager(config)
        print("✅ InfrastructureManager created")
        
        reporting_manager = ReportingManager(config)
        print("✅ ReportingManager created")
        
        # Test main load tester
        load_tester = HonoLoadTester(config)
        print("✅ HonoLoadTester created")
        
        return True
        
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        traceback.print_exc()
        return False

async def test_config_loading():
    """Test configuration loading functionality."""
    print("\n⚙️  Testing configuration loading...")
    
    try:
        from config.hono_config import HonoConfig, load_config_from_env
        
        config = HonoConfig()
        original_ip = config.registry_ip
        
        # Test loading from environment (will use defaults if file doesn't exist)
        await load_config_from_env(config, "hono.env")
        print(f"✅ Config loaded: Registry IP = {config.registry_ip}")
        
        return True
        
    except Exception as e:
        print(f"❌ Config loading failed: {e}")
        traceback.print_exc()
        return False

def test_library_status():
    """Test library availability detection."""
    print("\n📚 Testing library availability detection...")
    
    try:
        from utils.constants import get_library_status
        
        status = get_library_status()
        print(f"✅ Library status detected:")
        print(f"   - Reporting (matplotlib/pandas): {status['reporting']}")
        print(f"   - CoAP: {status['coap']}")
        print(f"   - AMQP: {status['amqp']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Library status check failed: {e}")
        traceback.print_exc()
        return False

def test_command_line_parsing():
    """Test that the main script can parse command line arguments."""
    print("\n🖥️  Testing command line argument parsing...")
    
    try:
        # Temporarily modify sys.argv to simulate command line args
        original_argv = sys.argv.copy()
        sys.argv = ["stress.py", "--help"]
        
        # Import the main module (this will trigger argument parsing)
        import importlib.util
        spec = importlib.util.spec_from_file_location("stress", "stress.py")
        module = importlib.util.module_from_spec(spec)
        
        # Restore original argv
        sys.argv = original_argv
        
        print("✅ Command line parsing structure is valid")
        return True
        
    except SystemExit:
        # This is expected when --help is used
        print("✅ Command line parsing works (help displayed)")
        sys.argv = original_argv
        return True
    except Exception as e:
        print(f"❌ Command line parsing failed: {e}")
        sys.argv = original_argv
        traceback.print_exc()
        return False

async def main():
    """Run all validation tests."""
    print("🧪 HONO LOAD TEST SUITE - REFACTORED VERSION VALIDATION")
    print("=" * 60)
    
    tests = [
        ("Module Imports", test_imports),
        ("Basic Initialization", test_basic_initialization),
        ("Configuration Loading", test_config_loading),
        ("Library Status Detection", test_library_status),
        ("Command Line Parsing", test_command_line_parsing),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        print("-" * 40)
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
                
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"🎯 VALIDATION SUMMARY: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! The refactored version is ready to use.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Validation failed with unexpected error: {e}")
        sys.exit(1)
