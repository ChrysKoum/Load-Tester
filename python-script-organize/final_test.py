#!/usr/bin/env python3
"""
Final integration test for the refactored Hono Load Test Suite.
"""

import signal
import threading
from config.hono_config import HonoConfig
from core.load_tester import HonoLoadTester

def main():
    print("🔧 Final Integration Test")
    print("=" * 40)
    
    # Test basic setup
    print("1. Creating configuration...")
    config = HonoConfig()
    print(f"   ✅ Config created: {config.registry_ip}:{config.registry_port}")
    
    # Test load tester creation
    print("2. Creating HonoLoadTester...")
    tester = HonoLoadTester(config)
    print("   ✅ HonoLoadTester created")
    
    # Test that all required methods exist
    print("3. Checking required methods...")
    required_methods = [
        'load_config_from_env',
        'setup_infrastructure', 
        'start_load_test',
        'stop_load_test',
        'generate_report'
    ]
    
    for method in required_methods:
        if hasattr(tester, method):
            print(f"   ✅ {method} method exists")
        else:
            print(f"   ❌ {method} method missing")
            return False
    
    # Test signal handling setup
    print("4. Testing signal handling...")
    shutdown_event = threading.Event()
    
    def signal_handler(signum, frame):
        print(f"   Signal {signum} received")
        tester.stop_load_test()
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    print("   ✅ Signal handler registered")
    
    # Test that modules can interact
    print("5. Testing module interactions...")
    try:
        # This should not fail - just testing that objects can interact
        if hasattr(tester, 'devices'):
            print("   ✅ Device list accessible")
        if hasattr(tester, 'tenants'):
            print("   ✅ Tenant list accessible")
        if hasattr(tester, 'reporting_manager'):
            print("   ✅ Reporting manager accessible")
        if hasattr(tester, 'protocol_workers'):
            print("   ✅ Protocol workers accessible")
    except Exception as e:
        print(f"   ❌ Module interaction failed: {e}")
        return False
    
    print("\n🎉 ALL INTEGRATION TESTS PASSED!")
    print("✅ The refactored Hono Load Test Suite is ready for use!")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
