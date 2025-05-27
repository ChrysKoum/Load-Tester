#!/usr/bin/env python3
"""
Hono Load Test Suite - Python Script (Refactored)
A comprehensive load testing tool for Eclipse Hono with multi-protocol support.

This is the refactored version with modular architecture for better maintainability.
"""

import sys
import asyncio
import argparse
import signal
import threading

from config.hono_config import HonoConfig
from core.load_tester import HonoLoadTester


def main():
    """Main entry point for the Hono Load Test Suite."""
    parser = argparse.ArgumentParser(description="Hono Load Test Suite")
    parser.add_argument("--mode", choices=["10fast", "100slow", "custom"], default="10fast",
                   help="Test mode: 10fast (10 devices, 5.75s interval), 100slow (100 devices, 60s interval), or custom")
    parser.add_argument("--protocols", nargs="+", choices=["mqtt", "http", "coap", "amqp", "lora"], 
                    default=["mqtt"], help="Protocols to use for testing")
    parser.add_argument("--kind", choices=["telemetry", "event"], default="telemetry",
                    help="Type of messages to send")
    parser.add_argument("--tenants", type=int, default=5, help="Number of tenants to create")
    parser.add_argument("--devices", type=int, help="Number of devices to create (overrides mode)")
    parser.add_argument("--interval", type=float, help="Message interval in seconds (overrides mode)")
    parser.add_argument("--env-file", default="hono.env", help="Environment file to load")
    parser.add_argument("--setup-only", action="store_true", help="Only setup infrastructure, don't run load test")
    parser.add_argument("--mqtt-insecure", action="store_true", help="Use insecure MQTT port (1883) instead of TLS")
    parser.add_argument("--no-ssl-verify", action="store_true", help="Disable SSL certificate verification")
    parser.add_argument("--tiny", action="store_true", help="Run a tiny test with 2 tenants and 2 devices")
    parser.add_argument("--report", action="store_true", help="Generate detailed test report with charts")
    parser.add_argument("--report-dir", default="./reports", help="Directory to save test reports")

    args = parser.parse_args()

    # Configure based on mode
    if args.tiny:
        num_devices = 2
        message_interval = 10.0
        args.tenants = 2
        print("Running in tiny test mode (2 tenants, 2 devices)")
    elif args.mode == "10fast":
        num_devices = args.devices or 10
        message_interval = args.interval or 5.75
    elif args.mode == "100slow":
        num_devices = args.devices or 100
        message_interval = args.interval or 60.0
    else:  # custom
        num_devices = args.devices or 10
        message_interval = args.interval or 10.0
    
    # Initialize tester
    config = HonoConfig()
    
    # Override TLS settings if requested
    if args.mqtt_insecure:
        config.use_mqtt_tls = False
    if args.no_ssl_verify:
        config.verify_ssl = False
    
    tester = HonoLoadTester(config)
    
    # Global variables for signal handling
    _shutdown_event = threading.Event()
    _generate_report_on_exit = args.report
    _report_dir = args.report_dir
    
    def signal_handler(signum, frame):
        """Handle interrupt signals gracefully."""
        print(f"\n🛑 Received signal {signum}. Initiating graceful shutdown...")
        tester.stop_load_test()
        _shutdown_event.set()
        
        # Generate report even if not originally requested when interrupted
        if tester.devices and len(tester.devices) > 0:
            print("📊 Generating report due to interruption...")
            try:
                tester.generate_report(_report_dir)
                print(f"✅ Report saved to: {_report_dir}")
            except Exception as e:
                print(f"⚠️ Failed to generate report: {e}")
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def run_test():
        # Load configuration
        await tester.load_config_from_env(args.env_file)
          # Setup infrastructure
        success = await tester.setup_infrastructure(args.tenants, num_devices)
        if not success:
            print("❌ Infrastructure setup failed!")
            return 1
        
        if args.setup_only:
            print("✅ Infrastructure setup complete. Use --setup-only=false to run load test.")
            return 0
        
        # Start load test
        print(f"\n🚀 Starting load test: {num_devices} devices, {message_interval}s interval")
        print(f"Protocols: {args.protocols}, Message type: {args.kind}")
        print("Press Enter when ready to start (Ctrl+C to stop and auto-generate report)...")
        input()
        
        try:
            tester.start_load_test(args.protocols, message_interval, args.kind)
            
            # Wait for shutdown signal or manual stop
            while not _shutdown_event.is_set():
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Load test interrupted by user")
            tester.stop_load_test()
        
        # Generate report if requested or if interrupted
        if args.report or _shutdown_event.is_set():
            print("📊 Generating final test report...")
            tester.generate_report(args.report_dir)
            print(f"✅ Test report generated in: {args.report_dir}")
        
        return 0
    
    try:
        exit_code = asyncio.run(run_test())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        # Ensure report generation on interruption
        if hasattr(tester, 'devices') and tester.devices and len(tester.devices) > 0:
            try:
                print("📊 Generating report due to interruption...")
                tester.generate_report(args.report_dir)
                print(f"✅ Report saved to: {args.report_dir}")
            except Exception as e:
                print(f"⚠️ Failed to generate report: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        # Try to generate report even on error if we have data
        if 'tester' in locals() and hasattr(tester, 'devices') and tester.devices and len(tester.devices) > 0:
            try:
                print("📊 Attempting to generate report despite error...")
                tester.generate_report(args.report_dir)
                print(f"✅ Report saved to: {args.report_dir}")
            except Exception as report_error:
                print(f"⚠️ Failed to generate report: {report_error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
