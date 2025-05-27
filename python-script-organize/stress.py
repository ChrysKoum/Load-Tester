#!/usr/bin/env python3
"""
Hono Load Test Suite - Python Script (Enhanced with Comprehensive Test Modes)
A comprehensive load testing tool for Eclipse Hono with multi-protocol support and endurance testing.
"""

import sys
import asyncio
import argparse
import signal
import threading
import time

from config.hono_config import HonoConfig
from config.test_modes import (
    TEST_MODES, get_mode_config, list_all_modes, validate_system_requirements, 
    get_intensity_color, get_endurance_warnings, TestIntensity
)
from core.load_tester import HonoLoadTester


def main():
    """Main entry point for the Hono Load Test Suite."""
    parser = argparse.ArgumentParser(description="Hono Load Test Suite - Comprehensive Test Modes")
    
    # Test mode selection with all new modes
    all_modes = list(TEST_MODES.keys()) + ["1", "2", "5", "10", "15", "25", "40", "50", "65", "75", "100", "150", 
                                          "burst", "oneday", "24h", "12h", "48h", "mqtt", "http"]
    parser.add_argument("--test-mode", choices=all_modes,
                       help="Pre-configured test mode (see --list-modes for all options)")
    parser.add_argument("--list-modes", action="store_true", help="List all available test modes and exit")
    
    # Legacy mode support
    parser.add_argument("--mode", choices=["10fast", "100slow", "custom"], default="10fast",
                   help="Legacy test mode (deprecated - use --test-mode instead)")
    
    # Custom overrides
    parser.add_argument("--protocols", nargs="+", choices=["mqtt", "http", "coap", "amqp", "lora"], 
                    help="Protocols to use (overrides test mode)")
    parser.add_argument("--kind", choices=["telemetry", "event"], default="telemetry",
                    help="Type of messages to send")
    parser.add_argument("--tenants", type=int, help="Number of tenants (overrides test mode)")
    parser.add_argument("--devices", type=int, help="Number of devices (overrides test mode)")
    parser.add_argument("--interval", type=float, help="Message interval in seconds (overrides test mode)")
    
    # Endurance test options
    parser.add_argument("--max-duration", type=float, help="Maximum test duration in hours (for endurance tests)")
    parser.add_argument("--auto-stop", action="store_true", help="Auto-stop test after target duration")
    
    # Configuration
    parser.add_argument("--env-file", default="hono.env", help="Environment file to load")
    parser.add_argument("--setup-only", action="store_true", help="Only setup infrastructure, don't run load test")
    parser.add_argument("--mqtt-insecure", action="store_true", help="Use insecure MQTT port (1883) instead of TLS")
    parser.add_argument("--no-ssl-verify", action="store_true", help="Disable SSL certificate verification")
    
    # Reporting
    parser.add_argument("--report", action="store_true", help="Generate detailed test report with charts")
    parser.add_argument("--report-dir", default="./reports", help="Directory to save test reports")
    parser.add_argument("--enhanced-stats", action="store_true", default=True, help="Show enhanced statistics output")
    parser.add_argument("--periodic-reports", type=int, help="Generate reports every N minutes (for endurance tests)")
    
    # Advanced Performance Monitoring
    parser.add_argument("--latency-sla", type=int, default=200, help="P95 latency SLA threshold in ms (default: 200)")
    parser.add_argument("--latency-sla-p99", type=int, default=500, help="P99 latency SLA threshold in ms (default: 500)")
    parser.add_argument("--success-sla", type=float, default=99.5, help="Success rate SLA threshold in percent (default: 99.5)")
    parser.add_argument("--real-time-monitoring", action="store_true", default=True, help="Enable real-time latency monitoring")
    parser.add_argument("--performance-alerts", action="store_true", help="Enable performance degradation alerts")
    
    # Legacy compatibility
    parser.add_argument("--tiny", action="store_true", help="Run a tiny test (equivalent to --test-mode dev)")

    args = parser.parse_args()

    # Handle mode listing
    if args.list_modes:
        list_all_modes()
        sys.exit(0)

    # Determine test configuration
    if args.test_mode:
        # Use predefined test mode
        mode = get_mode_config(args.test_mode)
        print(f"\n{get_intensity_color(mode.intensity)} Using test mode: {mode.name}")
        print(f"📝 {mode.description}")
        
        # Show endurance warnings if applicable
        endurance_warnings = get_endurance_warnings(mode)
        if endurance_warnings:
            for warning in endurance_warnings:
                print(warning)
        
        # Validate system requirements
        validation = validate_system_requirements(mode)
        if not validation["cpu_ok"] or not validation["memory_ok"]:
            print(f"\n⚠️  System Requirements Warning:")
            if not validation["cpu_ok"]:
                print(f"   CPU: {validation['cpu_count']} cores available, {validation['min_cpu']} recommended")
            if not validation["memory_ok"]:
                print(f"   Memory: {validation['memory_gb']:.1f}GB available, {validation['min_memory']}GB recommended")
            print(f"   You may experience performance issues or test failures.")
            
            if mode.intensity.value in ["stress", "extreme", "endurance"]:
                response = input("\n   Continue anyway? (y/N): ")
                if response.lower() != 'y':
                    print("   Test cancelled for safety.")
                    sys.exit(1)
        
        # Show disk space warning for endurance tests
        if mode.intensity == TestIntensity.ENDURANCE:
            disk_free = validation.get("disk_space_gb", 0)
            print(f"\n💾 Disk space available: {disk_free:.1f} GB")
            if disk_free < 10:
                print("   ⚠️  Low disk space - consider freeing space before long tests")
        
        num_devices = args.devices or mode.devices
        message_interval = args.interval or mode.message_interval
        num_tenants = args.tenants or mode.tenants
        protocols = args.protocols or mode.protocols
        
        print(f"\n⚙️  Configuration: {num_tenants} tenants, {num_devices} devices, {message_interval}s interval")
        print(f"🌐 Protocols: {', '.join(protocols)}")
        print(f"📊 Expected: {mode.expected_rps}, Memory: {mode.memory_usage}")
        
        # Show SLA thresholds
        print(f"\n🎯 Performance SLA Thresholds:")
        print(f"   P95 Latency: < {args.latency_sla}ms")
        print(f"   P99 Latency: < {args.latency_sla_p99}ms")
        print(f"   Success Rate: > {args.success_sla}%")
        
        # Show target duration for endurance tests
        if mode.target_duration_hours > 0:
            print(f"⏰ Target duration: {mode.target_duration_hours} hours")
            if args.auto_stop:
                print(f"   Auto-stop enabled after target duration")
        
    elif args.tiny:
        # Legacy tiny mode
        num_devices = 2
        message_interval = 10.0
        num_tenants = 2
        protocols = args.protocols or ["mqtt"]
        mode = None
        print("🧪 Running in legacy tiny test mode (2 tenants, 2 devices)")
        
    else:
        # Legacy mode handling
        if args.mode == "10fast":
            num_devices = args.devices or 10
            message_interval = args.interval or 5.75
            num_tenants = args.tenants or 5
        elif args.mode == "100slow":
            num_devices = args.devices or 100
            message_interval = args.interval or 60.0
            num_tenants = args.tenants or 15
        else:  # custom
            num_devices = args.devices or 10
            message_interval = args.interval or 10.0
            num_tenants = args.tenants or 5
        
        protocols = args.protocols or ["mqtt"]
        mode = None
        print(f"⚠️  Using legacy mode: {args.mode} (consider upgrading to --test-mode)")
    
    # Initialize tester
    config = HonoConfig()
    
    # Override TLS settings if requested
    if args.mqtt_insecure:
        config.use_mqtt_tls = False
    if args.no_ssl_verify:
        config.verify_ssl = False
    
    tester = HonoLoadTester(config)
    
    # Configure SLA thresholds in the tester's reporting manager
    if hasattr(tester, 'reporting_manager'):
        tester.reporting_manager.sla_thresholds = {
            'p95_latency_ms': args.latency_sla,
            'p99_latency_ms': args.latency_sla_p99,
            'success_rate_percent': args.success_sla,
            'min_throughput_rps': 10
        }
    
    # Global variables for signal handling and endurance testing
    _shutdown_event = threading.Event()
    _generate_report_on_exit = args.report
    _report_dir = args.report_dir
    _start_time = None
    _max_duration_seconds = None
    _performance_alerts_enabled = args.performance_alerts
    
    if args.max_duration:
        _max_duration_seconds = args.max_duration * 3600  # Convert hours to seconds
    elif mode and mode.target_duration_hours > 0 and args.auto_stop:
        _max_duration_seconds = mode.target_duration_hours * 3600

    def check_performance_alerts(tester):
        """Check for performance issues and alert if needed."""
        if not _performance_alerts_enabled or not hasattr(tester, 'reporting_manager'):
            return
        
        reporting_manager = tester.reporting_manager
        latency_stats = reporting_manager.get_real_time_latency_stats()
        
        if latency_stats and latency_stats['sample_size'] >= 10:
            p95 = latency_stats['percentiles'].get('p95', 0)
            p99 = latency_stats['percentiles'].get('p99', 0)
            
            # Check SLA violations
            if p95 > args.latency_sla:
                print(f"\n🚨 PERFORMANCE ALERT: P95 latency ({p95:.1f}ms) exceeds SLA ({args.latency_sla}ms)")
            
            if p99 > args.latency_sla_p99:
                print(f"\n🚨 PERFORMANCE ALERT: P99 latency ({p99:.1f}ms) exceeds SLA ({args.latency_sla_p99}ms)")
            
            # Check for degradation
            degradation = reporting_manager.check_performance_degradation()
            if degradation and degradation > 25:
                print(f"\n🚨 PERFORMANCE ALERT: Significant degradation detected ({degradation:+.1f}%)")

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
        nonlocal _start_time
        
        # Load configuration
        await tester.load_config_from_env(args.env_file)
        
        # Configure SLA thresholds after tester is initialized
        if hasattr(tester, 'reporting_manager'):
            tester.reporting_manager.sla_thresholds = {
                'p95_latency_ms': args.latency_sla,
                'p99_latency_ms': args.latency_sla_p99,
                'success_rate_percent': args.success_sla,
                'min_throughput_rps': 10
            }
        
        # Setup infrastructure
        success = await tester.setup_infrastructure(num_tenants, num_devices)
        if not success:
            print("❌ Infrastructure setup failed!")
            return 1
        
        if args.setup_only:
            print("✅ Infrastructure setup complete. Use without --setup-only to run load test.")
            return 0
        
        # Show test summary before starting
        print(f"\n🚀 Load Test Summary:")
        print(f"   Devices: {len(tester.devices)} across {len(tester.tenants)} tenants")
        print(f"   Protocols: {', '.join(protocols)}")
        print(f"   Message type: {args.kind}")
        print(f"   Interval: {message_interval}s between messages")
        print(f"   Real-time monitoring: {'Enabled' if args.real_time_monitoring else 'Disabled'}")
        print(f"   Performance alerts: {'Enabled' if args.performance_alerts else 'Disabled'}")
        
        if mode:
            print(f"   Expected duration: {mode.duration_hint}")
            print(f"   Expected throughput: {mode.expected_rps}")
            
            if mode.intensity == TestIntensity.ENDURANCE:
                print(f"   ⏰ This is an endurance test - monitor system resources")
                if _max_duration_seconds:
                    hours = _max_duration_seconds / 3600
                    print(f"   ⏱️  Auto-stop after: {hours:.1f} hours")
        
        print("\nPress Enter when ready to start (Ctrl+C to stop and auto-generate report)...")
        input()
        
        _start_time = time.time()
        
        try:
            tester.start_load_test(protocols, message_interval, args.kind)
            
            # For endurance tests, set up periodic reporting
            last_report_time = _start_time
            last_alert_check = _start_time
            report_interval = (args.periodic_reports * 60) if args.periodic_reports else 3600  # Default 1 hour
            alert_check_interval = 30  # Check for alerts every 30 seconds
            
            # Wait for shutdown signal, manual stop, or duration limit
            while not _shutdown_event.is_set():
                await asyncio.sleep(1)
                
                current_time = time.time()
                
                # Check duration limit
                if _max_duration_seconds and (current_time - _start_time) >= _max_duration_seconds:
                    print(f"\n⏰ Reached target duration of {_max_duration_seconds/3600:.1f} hours. Stopping test...")
                    tester.stop_load_test()
                    break
                
                # Performance alerts check
                if (args.performance_alerts and 
                    (current_time - last_alert_check) >= alert_check_interval):
                    check_performance_alerts(tester)
                    last_alert_check = current_time
                
                # Periodic reporting for endurance tests
                if (mode and mode.intensity == TestIntensity.ENDURANCE and 
                    (current_time - last_report_time) >= report_interval):
                    
                    elapsed_hours = (current_time - _start_time) / 3600
                    print(f"\n📊 Periodic Report - Elapsed: {elapsed_hours:.1f} hours")
                    
                    # Show current performance metrics
                    if hasattr(tester, 'reporting_manager'):
                        latency_stats = tester.reporting_manager.get_real_time_latency_stats()
                        if latency_stats:
                            print(f"   Current P95 latency: {latency_stats['percentiles'].get('p95', 0):.1f}ms")
                            print(f"   Current P99 latency: {latency_stats['percentiles'].get('p99', 0):.1f}ms")
                            print(f"   Current avg latency: {latency_stats['current_avg']:.1f}ms")
                    
                    # Generate intermediate report
                    if args.report or args.periodic_reports:
                        try:
                            tester.generate_report(args.report_dir)
                            print(f"   📁 Intermediate report saved to: {args.report_dir}")
                        except Exception as e:
                            print(f"   ⚠️ Failed to generate intermediate report: {e}")
                    
                    last_report_time = current_time
                
        except KeyboardInterrupt:
            print("\n🛑 Load test interrupted by user")
            tester.stop_load_test()
        
        # Final elapsed time
        if _start_time:
            total_elapsed = time.time() - _start_time
            elapsed_hours = total_elapsed / 3600
            print(f"\n⏱️  Total test duration: {elapsed_hours:.2f} hours ({total_elapsed:.1f} seconds)")
        
        # Generate final report if requested or if interrupted
        if args.report or _shutdown_event.is_set():
            print("📊 Generating final test report...")
            tester.generate_report(args.report_dir)
            print(f"✅ Final test report generated in: {args.report_dir}")
        
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
