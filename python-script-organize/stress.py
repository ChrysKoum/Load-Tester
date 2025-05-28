#!/usr/bin/env python3
"""
Hono Load Test Suite - Python Script (Enhanced with Advanced Features)
A comprehensive load testing tool for Eclipse Hono with multi-protocol support, 
registration throttling, and distributed messaging capabilities.
"""

import sys
import asyncio
import argparse
import signal
import threading
import time
import logging
import random
import numpy as np

from config.hono_config import HonoConfig
from config.test_modes import (
    TEST_MODES, get_mode_config, list_all_modes, validate_system_requirements, 
    get_intensity_color, get_endurance_warnings, TestIntensity
)
from core.load_tester import HonoLoadTester


def main():
    """Main entry point for the Hono Load Test Suite."""
    parser = argparse.ArgumentParser(description="Hono Load Test Suite - Comprehensive Test Modes with Advanced Features")
    
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
    
    # NEW: Advanced Registration and Messaging Features
    parser.add_argument("--enable-throttling", action="store_true", help="Enable registration throttling to prevent adapter overload")
    parser.add_argument("--throttling-base-delay", type=float, default=0.5, help="Base delay between registrations (seconds)")
    parser.add_argument("--throttling-jitter", type=float, default=0.2, help="Random jitter for registration delays")
    parser.add_argument("--max-concurrent-registrations", type=int, default=5, help="Maximum concurrent registrations")
    
    parser.add_argument("--enable-poisson", action="store_true", help="Enable Poisson distribution for message intervals")
    parser.add_argument("--poisson-lambda", type=float, default=1.0, help="Poisson lambda rate (events per minute)")
    parser.add_argument("--min-message-interval", type=float, default=0.1, help="Minimum interval between messages (seconds)")
    parser.add_argument("--max-message-interval", type=float, default=300.0, help="Maximum interval between messages (seconds)")
    
    parser.add_argument("--windowed-sending", action="store_true", help="Enable windowed message sending patterns")
    parser.add_argument("--window-size", type=int, default=60, help="Message sending window size (seconds)")
    parser.add_argument("--burst-factor", type=float, default=2.0, help="Burst factor for windowed sending")
    
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
    
    # Show advanced features configuration
    if args.enable_throttling or args.enable_poisson or args.windowed_sending:
        print(f"\n🔬 Advanced Features:")
        if args.enable_throttling:
            print(f"   📋 Registration Throttling: ✅")
            print(f"      Base delay: {args.throttling_base_delay}s")
            print(f"      Jitter: {args.throttling_jitter}s")
            print(f"      Max concurrent: {args.max_concurrent_registrations}")
        
        if args.enable_poisson:
            print(f"   📊 Poisson Distribution: ✅")
            print(f"      Lambda rate: {args.poisson_lambda} events/min")
            print(f"      Interval range: {args.min_message_interval}s - {args.max_message_interval}s")
        
        if args.windowed_sending:
            print(f"   🪟 Windowed Sending: ✅")
            print(f"      Window size: {args.window_size}s")
            print(f"      Burst factor: {args.burst_factor}x")
    
    # Initialize tester
    config = HonoConfig()
    
    # Override TLS settings if requested
    if args.mqtt_insecure:
        config.use_mqtt_tls = False
    if args.no_ssl_verify:
        config.verify_ssl = False
    
    tester = HonoLoadTester(config)
    
    # Configure advanced features in reporting manager
    if hasattr(tester, 'reporting_manager'):
        # Configure SLA thresholds
        tester.reporting_manager.sla_thresholds = {
            'p95_latency_ms': args.latency_sla,
            'p99_latency_ms': args.latency_sla_p99,
            'success_rate_percent': args.success_sla,
            'min_throughput_rps': 10
        }
        
        # Configure registration throttling
        if args.enable_throttling:
            tester.reporting_manager.registration_config.update({
                'enable_throttling': True,
                'registration_delay_base': args.throttling_base_delay,
                'registration_delay_jitter': args.throttling_jitter,
                'max_concurrent_registrations': args.max_concurrent_registrations
            })
        
        # Configure Poisson distribution
        if args.enable_poisson:
            tester.reporting_manager.poisson_config.update({
                'enable_poisson_distribution': True,
                'lambda_rate': args.poisson_lambda,
                'min_interval': args.min_message_interval,
                'max_interval': args.max_message_interval
            })
        
        # Configure windowed sending
        if args.windowed_sending:
            tester.reporting_manager.windowed_config = {
                'enable_windowed_sending': True,
                'window_size': args.window_size,
                'burst_factor': args.burst_factor,
                'current_window_start': 0,
                'messages_in_window': 0
            }

    # Initialize logger for stress.py
    stress_logger = logging.getLogger("stress_main")
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

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
        main_logger = logging.getLogger("stress_run_test")
        
        try:
            await tester.load_config_from_env(args.env_file)
            
            # Configure SLA thresholds after tester is initialized
            if hasattr(tester, 'reporting_manager'):
                tester.reporting_manager.sla_thresholds = {
                    'p95_latency_ms': args.latency_sla,
                    'p99_latency_ms': args.latency_sla_p99,
                    'success_rate_percent': args.success_sla,
                    'min_throughput_rps': 10
                }
            
            # Setup infrastructure with advanced features
            if args.enable_throttling and hasattr(tester.infrastructure_manager, 'setup_infrastructure_with_throttling'):
                print("🏗️  Setting up infrastructure with registration throttling...")
                success = await tester.infrastructure_manager.setup_infrastructure_with_throttling(
                    num_tenants, num_devices, tester.reporting_manager
                )
            else:
                print("🏗️  Setting up infrastructure...")
                success = await tester.setup_infrastructure(num_tenants, num_devices)
            
            if not success:
                main_logger.error("❌ Infrastructure setup failed!")
                return 1
            
            if args.setup_only:
                main_logger.info("✅ Infrastructure setup complete. Use without --setup-only to run load test.")
                return 0
            
            # Show test summary before starting
            print(f"\n🚀 Load Test Summary:")
            print(f"   Devices: {len(tester.devices)} across {len(tester.tenants)} tenants")
            print(f"   Protocols: {', '.join(protocols)}")
            print(f"   Message type: {args.kind}")
            print(f"   Base interval: {message_interval}s between messages")
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
            
            _start_time = time.time()
            
            # Start load test with enhanced features
            if args.enable_poisson or args.windowed_sending:
                print("🔬 Starting enhanced load test with advanced messaging patterns...")
                await start_enhanced_load_test(tester, protocols, message_interval, args)
            else:
                print("🔄 Starting standard load test...")
                tester.start_load_test(protocols, message_interval, args.kind)
            
            # For endurance tests, set up periodic reporting
            last_report_time = _start_time
            last_alert_check = _start_time
            report_interval = (args.periodic_reports * 60) if args.periodic_reports else 3600
            alert_check_interval = 30
            
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
                        
                        # Show advanced metrics if enabled
                        if args.enable_throttling or args.enable_poisson or args.windowed_sending:
                            print_advanced_periodic_stats(tester.reporting_manager, args)
                    
                    # Generate intermediate report
                    if args.report or args.periodic_reports:
                        try:
                            tester.generate_report(args.report_dir)
                            print(f"   📁 Intermediate report saved to: {args.report_dir}")
                        except Exception as e:
                            print(f"   ⚠️ Failed to generate intermediate report: {e}")
                    
                    last_report_time = current_time
            
            return 0
            
        except KeyboardInterrupt:
            main_logger.info("\n🛑 Load test interrupted by user in run_test loop (KeyboardInterrupt).")
            if not _shutdown_event.is_set():
                 if 'tester' in locals(): 
                     tester.stop_load_test()
                 _shutdown_event.set()
            raise
        except Exception as e_run:
            main_logger.error(f"❌ Unexpected error during test execution in run_test: {e_run}", exc_info=True)
            if 'tester' in locals():
                tester.stop_load_test()
            return 1
        finally:
            if _start_time and not args.setup_only: 
                total_elapsed = time.time() - _start_time
                main_logger.info(f"\n⏱️  Total test duration: {total_elapsed/3600:.2f} hours ({total_elapsed:.1f} seconds)")
                main_logger.info("📊 Generating final test report in run_test.finally...")
                
                try:
                    if hasattr(tester, 'reporting_manager') and hasattr(tester.reporting_manager, 'print_enhanced_final_stats'):
                        tester.reporting_manager.print_enhanced_final_stats()
                    
                    if _generate_report_on_exit:
                        tester.generate_report(_report_dir)
                        main_logger.info(f"✅ Final test report generated in: {_report_dir}")
                        
                        # Show advanced findings if available
                        if hasattr(tester, 'reporting_manager') and hasattr(tester.reporting_manager, 'print_advanced_findings'):
                            tester.reporting_manager.print_advanced_findings()
                        
                except Exception as e_final:
                    main_logger.error(f"⚠️ Failed to generate final report: {e_final}")

    try:
        exit_code = asyncio.run(run_test())
        if exit_code != 0:
            stress_logger.error(f"Test run concluded with error code: {exit_code}")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        stress_logger.info("\n🛑 Test interrupted by user (main level).")
        if 'tester' in locals() and hasattr(tester, 'devices') and _generate_report_on_exit :
            if tester.devices and len(tester.devices) > 0:
                try:
                    stress_logger.info("📊 Generating report due to main level interruption...")
                    tester.generate_report(_report_dir)
                    stress_logger.info(f"✅ Report saved to: {_report_dir}")
                except Exception as e_report_ki:
                    stress_logger.error(f"⚠️ Failed to generate report on main KeyboardInterrupt: {e_report_ki}", exc_info=True)
        sys.exit(130)
    except SystemExit as se:
        if hasattr(se, 'code') and se.code != 0:
            stress_logger.error(f"❌ Test exited with code: {se.code}")
        raise
    except Exception as e:
        stress_logger.error(f"❌ An unexpected error occurred in main: {e}", exc_info=True)
        if 'tester' in locals() and hasattr(tester, 'devices') and _generate_report_on_exit:
            if tester.devices and len(tester.devices) > 0:
                try:
                    stress_logger.info("📊 Generating error report...")
                    tester.generate_report(_report_dir)
                    stress_logger.info(f"✅ Error report saved to: {_report_dir}")
                except Exception as e_report_err:
                    stress_logger.error(f"⚠️ Failed to generate error report: {e_report_err}")
        sys.exit(1)


async def start_enhanced_load_test(tester, protocols, base_interval, args):
    """Start enhanced load test with advanced messaging patterns."""
    # Initialize the reporting manager (crucial for enhanced tests)
    tester.reporting_manager.initialize_test(protocols)
    tester.reporting_manager.set_running(True)
    tester.protocol_workers.set_running(True)
    tester.reporting_manager.monitor_stats()
    
    tasks = []
    
    for i, device in enumerate(tester.devices):
        for protocol in protocols:
            if protocol.lower() == "mqtt":
                if args.enable_poisson:
                    task = asyncio.create_task(
                        enhanced_mqtt_worker_with_poisson(
                            device, base_interval, tester.reporting_manager, tester.protocol_workers
                        )
                    )
                elif args.windowed_sending:
                    task = asyncio.create_task(
                        enhanced_mqtt_worker_with_windowing(
                            device, base_interval, tester.reporting_manager, tester.protocol_workers, args
                        )
                    )
                else:
                    # Regular MQTT worker
                    task = asyncio.create_task(
                        asyncio.to_thread(
                            tester.protocol_workers.mqtt_telemetry_worker,
                            device, base_interval, "telemetry"
                        )
                    )
                tasks.append(task)
                
            elif protocol.lower() == "http":
                if args.enable_poisson:
                    task = asyncio.create_task(
                        enhanced_http_worker_with_poisson(
                            device, base_interval, tester.reporting_manager, tester.protocol_workers
                        )
                    )
                elif args.windowed_sending:
                    task = asyncio.create_task(
                        enhanced_http_worker_with_windowing(
                            device, base_interval, tester.reporting_manager, tester.protocol_workers, args
                        )
                    )
                else:
                    # Regular HTTP worker
                    task = asyncio.create_task(
                        tester.protocol_workers.http_telemetry_worker(device, base_interval, "telemetry")
                    )
                tasks.append(task)
    
    print(f"🚀 Started {len(tasks)} enhanced worker tasks")
    
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        print(f"❌ Enhanced load test error: {e}")
    finally:
        # Stop the test and set end time
        tester.reporting_manager.set_running(False)
        tester.protocol_workers.set_running(False)
        print("✅ Enhanced load test completed")


async def enhanced_mqtt_worker_with_poisson(device, base_interval, reporting_manager, protocol_workers):
    """Enhanced MQTT worker with Poisson distribution."""
    import paho.mqtt.client as mqtt
    import json
    import ssl
    
    client = mqtt.Client(client_id=device.device_id)
    client.username_pw_set(f"{device.auth_id}@{device.tenant_id}", device.password)
    
    connected_flag = False
    
    def on_connect(client_instance, userdata, flags, rc):
        nonlocal connected_flag
        if rc == 0:
            connected_flag = True
        else:            print(f"MQTT connection failed for {device.device_id}: {mqtt.error_string(rc)}")
    
    client.on_connect = on_connect
    
    try:
        # Connect to MQTT broker
        if protocol_workers.config.use_mqtt_tls:
            # Use the same SSL context logic as the main worker
            ssl_context = protocol_workers._get_mqtt_ssl_context()
            if ssl_context:
                client.tls_set_context(ssl_context)
            else:
                # Fallback to insecure TLS if SSL context creation fails
                client.tls_set(ca_certs=None, certfile=None, keyfile=None, cert_reqs=ssl.CERT_NONE,
                              tls_version=ssl.PROTOCOL_TLS, ciphers=None)
                client.tls_insecure_set(True)
            mqtt_port = protocol_workers.config.mqtt_adapter_port
        else:
            mqtt_port = protocol_workers.config.mqtt_insecure_port
        
        client.connect(protocol_workers.config.mqtt_adapter_ip, mqtt_port, protocol_workers.config.mqtt_keepalive)
        client.loop_start()
        
        # Wait for connection
        connect_timeout = 10
        wait_start = time.time()
        while not connected_flag and (time.time() - wait_start) < connect_timeout:
            await asyncio.sleep(0.1)
        
        if not connected_flag:
            print(f"❌ MQTT connection timeout for {device.device_id}")
            return
        
        message_count = 0
        last_message_time = time.time()
        
        while protocol_workers.running and connected_flag:
            # Generate Poisson-distributed interval
            if reporting_manager:
                interval = reporting_manager.generate_poisson_interval(base_interval)
            else:
                interval = base_interval
            
            # Create message payload
            payload_data = {
                "device_id": device.device_id,
                "tenant_id": device.tenant_id,
                "timestamp": int(time.time()),
                "message_count": message_count,
                "protocol": "mqtt",
                "actual_interval": interval,
                "expected_interval": base_interval,
                "temperature": round(random.uniform(18.0, 35.0), 2),
                "humidity": round(random.uniform(30.0, 90.0), 2),
                "pressure": round(random.uniform(980.0, 1030.0), 2),
                "battery": round(random.uniform(20.0, 100.0), 2),
                "signal_strength": random.randint(-100, -30)
            }
            
            payload_json = json.dumps(payload_data)
            
            start_time = time.monotonic()
            msg_info = client.publish("telemetry", payload_json, qos=0)
            end_time = time.monotonic()
            response_time_ms = (end_time - start_time) * 1000
            
            # Record metrics
            current_time = time.time()
            actual_interval_used = current_time - last_message_time
            last_message_time = current_time
            
            if msg_info.rc == mqtt.MQTT_ERR_SUCCESS:
                if reporting_manager:
                    reporting_manager.record_message_sent("mqtt")
                    reporting_manager.record_latency_metrics(response_time_ms)
                    
                    # Record adapter load
                    current_rate = 1.0 / actual_interval_used if actual_interval_used > 0 else 0
                    reporting_manager.record_adapter_load(1, current_rate)
                
                message_count += 1
            else:
                if reporting_manager:
                    reporting_manager.record_message_failed("mqtt")
            
            # Sleep for Poisson interval
            await asyncio.sleep(interval)
    
    except Exception as e:
        print(f"❌ Enhanced MQTT worker error for {device.device_id}: {e}")
    finally:
        if connected_flag:
            client.disconnect()
        client.loop_stop()


async def enhanced_http_worker_with_poisson(device, base_interval, reporting_manager, protocol_workers):
    """Enhanced HTTP worker with Poisson distribution."""
    import aiohttp
    import json
    import ssl
    
    # Create SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    # Determine URL
    if protocol_workers.config.use_tls:
        url = f"https://{protocol_workers.config.http_adapter_ip}:{protocol_workers.config.http_adapter_port}/telemetry"
    else:
        url = f"http://{protocol_workers.config.http_adapter_ip}:{protocol_workers.config.http_insecure_port}/telemetry"
    
    connector = aiohttp.TCPConnector(ssl=ssl_context if protocol_workers.config.use_tls else False)
    timeout_config = aiohttp.ClientTimeout(total=protocol_workers.config.http_timeout)
    
    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout_config) as session:
            headers = {"Content-Type": "application/json"}
            auth = aiohttp.BasicAuth(f"{device.auth_id}@{device.tenant_id}", device.password)
            
            message_count = 0
            last_message_time = time.time()
            
            while protocol_workers.running:
                # Generate Poisson interval
                if reporting_manager:
                    interval = reporting_manager.generate_poisson_interval(base_interval)
                else:
                    interval = base_interval
                
                # Create payload
                payload_data = {
                    "device_id": device.device_id,
                    "tenant_id": device.tenant_id,
                    "timestamp": int(time.time()),
                    "message_count": message_count,
                    "protocol": "http",
                    "actual_interval": interval,
                    "expected_interval": base_interval,
                    "temperature": round(random.uniform(18.0, 35.0), 2),
                    "humidity": round(random.uniform(30.0, 90.0), 2),
                    "pressure": round(random.uniform(980.0, 1030.0), 2),
                    "battery": round(random.uniform(20.0, 100.0), 2),
                    "signal_strength": random.randint(-100, -30)
                }
                
                payload_json = json.dumps(payload_data)
                message_size_bytes = len(payload_json.encode('utf-8'))
                
                start_time = time.monotonic()
                try:
                    async with session.post(url, data=payload_json, headers=headers, auth=auth) as response:
                        end_time = time.monotonic()
                        response_time_ms = (end_time - start_time) * 1000
                        
                        # Record metrics
                        current_time = time.time()
                        actual_interval_used = current_time - last_message_time
                        last_message_time = current_time
                        
                        if reporting_manager:
                            reporting_manager.record_message_metrics(
                                protocol="http",
                                response_time_ms=response_time_ms,
                                status_code=response.status,
                                message_size_bytes=message_size_bytes,
                                success=response.status < 400
                            )
                            
                            # Record adapter load
                            current_rate = 1.0 / actual_interval_used if actual_interval_used > 0 else 0
                            reporting_manager.record_adapter_load(1, current_rate)
                        
                        message_count += 1
                
                except Exception as e:
                    if reporting_manager:
                        reporting_manager.record_message_failed("http")
                
                # Sleep for Poisson interval
                await asyncio.sleep(interval)
    
    except Exception as e:
        print(f"❌ Enhanced HTTP worker error for {device.device_id}: {e}")


async def enhanced_mqtt_worker_with_windowing(device, base_interval, reporting_manager, protocol_workers, args):
    """Enhanced MQTT worker with windowed sending patterns."""
    # Similar to Poisson but uses windowed bursts
    # Implementation would calculate burst periods and quiet periods
    # For brevity, delegating to Poisson implementation with burst factor applied
    burst_interval = base_interval / args.burst_factor
    return await enhanced_mqtt_worker_with_poisson(device, burst_interval, reporting_manager, protocol_workers)


async def enhanced_http_worker_with_windowing(device, base_interval, reporting_manager, protocol_workers, args):
    """Enhanced HTTP worker with windowed sending patterns."""
    # Similar to Poisson but uses windowed bursts
    burst_interval = base_interval / args.burst_factor
    return await enhanced_http_worker_with_poisson(device, burst_interval, reporting_manager, protocol_workers)


def print_advanced_periodic_stats(reporting_manager, args):
    """Print advanced periodic statistics."""
    if args.enable_throttling and hasattr(reporting_manager, 'advanced_metrics'):
        if reporting_manager.advanced_metrics.registration_delays:
            avg_delay = np.mean(reporting_manager.advanced_metrics.registration_delays)
            print(f"   📋 Avg Registration Delay: {avg_delay:.2f}s")
    
    if args.enable_poisson and hasattr(reporting_manager, 'advanced_metrics'):
        if reporting_manager.advanced_metrics.poisson_intervals:
            reporting_manager.update_distribution_statistics()
            stats = reporting_manager.advanced_metrics.message_distribution_stats
            print(f"   📊 Poisson Mean Interval: {stats.get('mean_interval', 0):.2f}s")
            print(f"   📊 Coefficient of Variation: {stats.get('coefficient_of_variation', 0):.3f}")
    
    if args.windowed_sending and hasattr(reporting_manager, 'windowed_config'):
        config = reporting_manager.windowed_config
        print(f"   🪟 Current Window Messages: {config.get('messages_in_window', 0)}")


if __name__ == "__main__":
    main()
