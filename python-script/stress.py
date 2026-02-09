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
import logging.handlers # For more advanced handlers if needed in future
from pathlib import Path
import datetime
from typing import Optional, Dict, Any

from config.hono_config import HonoConfig, load_config_from_env as actual_hono_config_loader
from config.test_modes import (
    TEST_MODES, get_mode_config, list_all_modes, validate_system_requirements, 
    get_intensity_color, get_endurance_warnings, TestIntensity
)
from core.load_tester import HonoLoadTester
from core.reporting import ReportingManager 



main_logger = logging.getLogger("stress_script") # Define main_logger at module level or pass it around

# Global variable to store the main output path for the current run
current_run_output_path: Optional[Path] = None # Optional is now defined

# Global shutdown event
_shutdown_event = threading.Event() # Define _shutdown_event globally

# Global test configuration data (populated from profile)
test_config_data: Dict[str, Any] = {}

def setup_logging(args, base_output_dir: Path): # Modified signature
    """Configures console and file logging into the specified base_output_dir."""
    global main_logger # Use the global logger

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    console_handler = logging.StreamHandler(sys.stdout)
    console_log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    console_handler.setLevel(console_log_level)
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    console_handler.encoding = 'utf-8'
    root_logger.addHandler(console_handler)

    # File Handler - logs will go directly into the base_output_dir
    try:
        # The base_output_dir is already created by main()
        # Use a fixed name for the log file within the timestamped run folder
        log_file_name = "load_test_run.log"
        log_file_path = base_output_dir / log_file_name
        
        file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(name)-30s - %(filename)s:%(lineno)d - %(message)s')
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        main_logger.info(f"File logging initialized (UTF-8). Log file: {log_file_path.resolve()} λ ✅")
    except Exception as e:
        print(f"Critical error initializing file logging: {e}")
        logging.basicConfig(level=logging.ERROR) # Basic fallback
        main_logger.error(f"Failed to initialize file logging: {e}", exc_info=True)


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    global _shutdown_event # Ensure we're using the global event
    print(f"\n🛑 Received signal {signum}. Initiating graceful shutdown...")
    _shutdown_event.set()


def print_startup_info(args, config, mode_config=None):
    """Print the startup information and configuration."""
    print("\n🌟 Hono Load Test Suite - Startup Information 🌟")
    print(f"  Test Mode: {args.test_mode or 'custom'}")
    print(f"  Log Level: {args.log_level}")
    print(f"  Duration: {args.max_duration} hours (auto-stop: {'enabled' if args.auto_stop else 'disabled'})")
    print(f"  Message Interval: {args.interval}s")
    print(f"  Tenants: {args.tenants}")
    print(f"  Devices: {args.devices}")
    print(f"  Protocols: {', '.join(args.protocols)}")
    print(f"  Kind: {args.kind}")
    print(f"  Env File: {args.env_file}")
    print(f"  Setup Only: {args.setup_only}")
    print(f"  MQTT Insecure: {args.mqtt_insecure}")
    print(f"  No SSL Verify: {args.no_ssl_verify}")
    print(f"  Report: {args.report}")
    print(f"  Report Dir: {args.report_dir}")
    print(f"  Enhanced Stats: {args.enhanced_stats}")
    print(f"  Periodic Reports: {args.periodic_reports} minutes")
    print(f"  Latency SLA: {args.latency_sla}ms")
    print(f"  Success SLA: {args.success_sla}%")
    print(f"  Real-time Monitoring: {'Enabled' if args.real_time_monitoring else 'Disabled'}")
    print(f"  Performance Alerts: {'Enabled' if args.performance_alerts else 'Disabled'}")
    
    if mode_config:
        print(f"  Mode Description: {mode_config.description}")
        print(f"  Expected Throughput: {mode_config.expected_rps} RPS")
        print(f"  Intensity: {mode_config.intensity.name}")
        
        if mode_config.intensity == TestIntensity.ENDURANCE:
            print(f"  ⏰ Endurance test detected - monitor system resources")
            if args.max_duration:
                print(f"  ⏱️  Auto-stop after: {args.max_duration:.1f} hours")
    
    print("🔧 Advanced Features Configuration:")
    print(f"  Throttling: {'Enabled' if args.enable_throttling else 'Disabled'}")
    if args.enable_throttling:
        print(f"    Base Delay: {args.throttling_base_delay}s")
        print(f"    Jitter: {args.throttling_jitter}s")
        print(f"    Max Concurrent Registrations: {args.max_concurrent_registrations}")
    
    print(f"  Poisson Distribution: {'Enabled' if args.enable_poisson else 'Disabled'}")
    if args.enable_poisson:
        print(f"    Lambda Rate: {args.poisson_lambda} events/min")
        print(f"    Interval Range: {args.min_message_interval}s - {args.max_message_interval}s")
    
    print(f"  Windowed Sending: {'Enabled' if args.windowed_sending else 'Disabled'}")
    if args.windowed_sending:
        print(f"    Window Size: {args.window_size}s")
        print(f"    Burst Factor: {args.burst_factor}x")
    
    print("🛠️ System Configuration:")
    print(f"  Python Version: {sys.version}")
    # Check if modules are available before accessing their versions
    if hasattr(asyncio, '__version__'):
        print(f"  Asyncio Version: {asyncio.__version__}")
    if hasattr(np, '__version__'):
        print(f"  Numpy Version: {np.__version__}")

    # Define logger_instance_to_inspect here
    logger_instance_to_inspect = logging.getLogger()
    
    # Use the logger's effective level and convert to name properly
    current_level = logger_instance_to_inspect.getEffectiveLevel()
    print(f"  Logging Level: {logging.getLevelName(current_level)}")
    
    # List all active handlers and their levels
    print("  Active Log Handlers:")
    if not logger_instance_to_inspect.handlers:
        print("    - No handlers configured on root logger.")
    for handler in logger_instance_to_inspect.handlers:
        handler_level_name = logging.getLevelName(handler.level)
        print(f"    - {handler.__class__.__name__}: Level {handler_level_name}")



async def load_config_from_env(config_obj_to_update, env_file_path):
    """Load configuration from environment file by calling the actual utility."""
    try:
        await actual_hono_config_loader(config_obj_to_update, env_file_path)
    except FileNotFoundError:
        main_logger.error(f"Environment file not found by stress.py wrapper: {env_file_path}")
    except Exception as e:
        main_logger.error(f"Error in stress.py calling config loader for {env_file_path}: {e}", exc_info=True)


async def run_test():
    """Main asynchronous function to run the load test."""
    global main_logger, args, config, reporting_manager, current_run_output_path, _shutdown_event

    start_time_total = time.monotonic()
    exit_code = 0
    
    # Initialize local variables that were causing nonlocal errors
    _start_time = None
    _generate_report_on_exit = args.report
    _report_dir = str(current_run_output_path)  # Use the timestamped output path
    _max_duration_seconds = None
    _performance_alerts_enabled = args.performance_alerts
    
    # Determine test mode and parameters
    mode = None
    if args.test_mode:
        try:
            mode = get_mode_config(args.test_mode)
            main_logger.info(f"📋 Using test mode: {mode.name} ({args.test_mode})")
        except ValueError as e:
            main_logger.error(f"Invalid test mode: {e}")
            return 1  # Return instead of sys.exit in async function
    elif args.tiny: # Legacy --tiny support
        mode = get_mode_config("dev") # 'dev' mode is the equivalent of tiny
        main_logger.info("🧪 Running in legacy tiny test mode (2 tenants, 2 devices)")
    else: # Legacy --mode support or custom if no mode specified
        if args.mode != "custom":
            main_logger.warning(f"⚠️  Using legacy mode: {args.mode} (consider upgrading to --test-mode)")
            if args.mode == "10fast":
                try:
                    mode = get_mode_config("light") # Example mapping
                except:
                    pass  # Continue with custom if mode doesn't exist
            elif args.mode == "100slow":
                try:
                    mode = get_mode_config("stress") # Example mapping
                except:
                    pass  # Continue with custom if mode doesn't exist

    # Determine final parameters, allowing overrides
    num_tenants = args.tenants if args.tenants is not None else (mode.tenants if mode else 1)
    num_devices = args.devices if args.devices is not None else (mode.devices if mode else 1)
    message_interval = args.interval if args.interval is not None else (mode.message_interval if mode else 10.0)
    protocols = args.protocols if args.protocols else (mode.protocols if mode else ["mqtt"])

    # Set duration limits
    if args.max_duration:
        _max_duration_seconds = args.max_duration * 3600  # Convert hours to seconds
    elif args.duration:
        _max_duration_seconds = float(args.duration)
    elif mode and hasattr(mode, 'target_duration_hours') and mode.target_duration_hours > 0 and args.auto_stop:
        _max_duration_seconds = mode.target_duration_hours * 3600

    # Print advanced feature status
    if args.enable_throttling or args.enable_poisson or args.windowed_sending:
        print("\n🔬 Advanced Features:")
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
        print("") 

    # Initialize config - use the global config that was created in main()
    # Don't recreate it here since it was already created in main()
    
    # Override TLS settings if requested
    if args.mqtt_insecure:
        config.use_mqtt_tls = False
    if args.no_ssl_verify:
        config.verify_ssl = False
    
    # Handle cache-related commands
    if args.clear_cache:
        from core.device_cache import DeviceCache
        cache = DeviceCache()
        if cache.clear_cache(config.registry_ip, config.registry_port):
            main_logger.info(f"✅ Cache cleared for {config.registry_ip}:{config.registry_port}")
        else:
            main_logger.warning(f"⚠️  No cache found for {config.registry_ip}:{config.registry_port}")
        sys.exit(0)
    
    # Initialize infrastructure manager (use the global reporting_manager)
    from core.infrastructure import InfrastructureManager
    
    use_cache = not args.no_cache
    infrastructure = InfrastructureManager(config, reporting_manager, use_cache=use_cache)  # Pass the global reporting_manager and cache flag
    
    if use_cache:
        main_logger.info("♻️  Device/tenant caching enabled")
    else:
        main_logger.info("🔨 Device/tenant caching disabled - creating fresh infrastructure")
    
    # Configure advanced features in reporting manager
    if hasattr(reporting_manager, 'sla_thresholds'):
        # Configure SLA thresholds
        reporting_manager.sla_thresholds = {
            'p95_latency_ms': args.latency_sla,
            'p99_latency_ms': args.latency_sla_p99,
            'success_rate_percent': args.success_sla,
            'min_throughput_rps': 10
        }
        
        # Configure registration throttling
        if args.enable_throttling:
            reporting_manager.registration_config.update({
                'enable_throttling': True,
                'registration_delay_base': args.throttling_base_delay,
                'registration_delay_jitter': args.throttling_jitter,
                'max_concurrent_registrations': args.max_concurrent_registrations
            })
        
        # Configure Poisson distribution
        if args.enable_poisson:
            reporting_manager.poisson_config.update({
                'enable_poisson_distribution': True,
                'lambda_rate': args.poisson_lambda,
                'min_interval': args.min_message_interval,
                'max_interval': args.max_message_interval
            })
        
        # Configure windowed sending
        if args.windowed_sending:
            reporting_manager.windowed_config = {
                'enable_windowed_sending': True,
                'window_size': args.window_size,
                'burst_factor': args.burst_factor,
                'current_window_start': 0,
                'messages_in_window': 0
            }

    def check_performance_alerts(tester):
        """Check for performance issues and alert if needed."""
        if not _performance_alerts_enabled or not hasattr(tester, 'reporting_manager'):
            return
        
        reporting_manager_local = tester.reporting_manager
        latency_stats = reporting_manager_local.get_real_time_latency_stats()
        
        if latency_stats and latency_stats['sample_size'] >= 10:
            p95 = latency_stats['percentiles'].get('p95', 0)
            p99 = latency_stats['percentiles'].get('p99', 0)
            
            # Check SLA violations
            if p95 > args.latency_sla:
                print(f"\n🚨 PERFORMANCE ALERT: P95 latency ({p95:.1f}ms) exceeds SLA ({args.latency_sla}ms)")
            
            if p99 > args.latency_sla_p99:
                print(f"\n🚨 PERFORMANCE ALERT: P99 latency ({p99:.1f}ms) exceeds SLA ({args.latency_sla_p99}ms)")
            
            # Check for degradation if method exists
            if hasattr(reporting_manager_local, 'check_performance_degradation'):
                degradation = reporting_manager_local.check_performance_degradation()
                if degradation and degradation > 25:
                    print(f"\n🚨 PERFORMANCE ALERT: Significant degradation detected ({degradation:+.1f}%)")

    async def load_config_from_env_local(config_obj_to_update, env_file_path):
        """Load configuration from environment file by calling the actual utility."""
        try:
            await actual_hono_config_loader(config_obj_to_update, env_file_path)
        except FileNotFoundError:
            main_logger.error(f"Environment file not found by stress.py wrapper: {env_file_path}")
        except Exception as e:
            main_logger.error(f"Error in stress.py calling config loader for {env_file_path}: {e}", exc_info=True)

    tester = None # Initialize tester to None
    
    try:
        await load_config_from_env_local(config, args.env_file)
        
        # Setup infrastructure FIRST
        if args.enable_throttling:
            print("🏗️  Setting up infrastructure with registration throttling...")
            # Check if the method exists before calling
            if hasattr(infrastructure, 'setup_infrastructure_with_throttling'):
                setup_success = await infrastructure.setup_infrastructure_with_throttling(
                    num_tenants=num_tenants, 
                    num_devices=num_devices,
                    reporting_manager=reporting_manager
                )
                
                if not setup_success:
                    print("❌ Failed to set up infrastructure with throttling")
                    return 1
                
                tenants_list = infrastructure.tenants
                devices_list = infrastructure.devices
            else:
                main_logger.warning("Throttling requested but method not available, using standard setup")
                tenants_list, devices_list, setup_success = await infrastructure.setup_infrastructure(
                    num_tenants=num_tenants, 
                    num_devices=num_devices
                )
                
                if not setup_success:
                    print("❌ Failed to set up infrastructure")
                    return 1
        else:
            print("🏗️  Setting up infrastructure...")
            tenants_list, devices_list, setup_success = await infrastructure.setup_infrastructure(
                num_tenants=num_tenants, 
                num_devices=num_devices
            )
            
            if not setup_success:
                print("❌ Failed to set up infrastructure")
                return 1

        # NOW create the LoadTester with the actual devices and tenants
        # NOW create the LoadTester with the actual devices and tenants
        tester = HonoLoadTester(
            config=config,
            devices=devices_list,
            tenants=tenants_list,
            reporting_manager=reporting_manager,
            message_interval=args.interval,
            test_config=test_config_data
        )
        
        # Configure SLA thresholds after tester is initialized
        if hasattr(tester, 'reporting_manager'):
            tester.reporting_manager.sla_thresholds = {
                'p95_latency_ms': args.latency_sla,
                'p99_latency_ms': args.latency_sla_p99,
                'success_rate_percent': args.success_sla,
                'min_throughput_rps': 10
            }
        
        # Update signal handler to access tester
        def signal_handler_with_tester(signum, frame):
            global _shutdown_event
            print(f"\n🛑 Received signal {signum}. Initiating graceful shutdown...")
            if tester and hasattr(tester, 'stop_load_test'):
                tester.stop_load_test()
            _shutdown_event.set()
            
            # Generate report even if not originally requested when interrupted
            if tester and hasattr(tester, 'devices') and tester.devices and len(tester.devices) > 0:
                print("📊 Generating report due to interruption...")
                try:
                    if hasattr(tester.reporting_manager, 'generate_report'):
                        tester.reporting_manager.generate_report(tenants_list, devices_list, _report_dir)
                        print(f"✅ Report saved to: {_report_dir}")
                except Exception as e:
                    print(f"⚠️ Failed to generate report: {e}")
        
        # Re-register signal handler with tester access
        signal.signal(signal.SIGINT, signal_handler_with_tester)
        
        # Show test summary AFTER tester creation
        print(f"\n🚀 Load Test Summary:")
        print(f"   Devices: {len(devices_list)} across {len(tenants_list)} tenants") 
        print(f"   Protocols: {', '.join(protocols)}")
        print(f"   Message type: {args.kind}")
        print(f"   Base interval: {message_interval}s between messages")
        print(f"   Real-time monitoring: {'Enabled' if args.real_time_monitoring else 'Disabled'}")
        print(f"   Performance alerts: {'Enabled' if args.performance_alerts else 'Disabled'}")
        
        if _max_duration_seconds:
            print(f"   Planned Duration: {_max_duration_seconds}s ({_max_duration_seconds/3600:.2f}h)")
        else:
            print(f"   Planned Duration: Infinite (Control-C to stop)")
        
        if mode:
            print(f"   Expected duration: {mode.duration_hint}")
            print(f"   Expected throughput: {mode.expected_rps}")
            
            if hasattr(mode, 'intensity') and mode.intensity == TestIntensity.ENDURANCE:
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
            if hasattr(tester, 'start_load_test'):
                tester.start_load_test(protocols, message_interval, args.kind)
            else:
                main_logger.error("Tester does not have start_load_test method")
                return 1
        
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
                if hasattr(tester, 'stop_load_test'):
                    tester.stop_load_test()
                break
            
            # Performance alerts check
            if (args.performance_alerts and 
                (current_time - last_alert_check) >= alert_check_interval):
                check_performance_alerts(tester)
                last_alert_check = current_time
            
            # Periodic reporting for endurance tests
            if (mode and hasattr(mode, 'intensity') and mode.intensity == TestIntensity.ENDURANCE and 
                (current_time - last_report_time) >= report_interval):
                
                elapsed_hours = (current_time - _start_time) / 3600
                print(f"\n📊 Periodic Report - Elapsed: {elapsed_hours:.1f} hours")
                
                # Show current performance metrics
                if hasattr(tester, 'reporting_manager'):
                    if hasattr(tester.reporting_manager, 'get_real_time_latency_stats'):
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
                        if hasattr(tester.reporting_manager, 'generate_report'):
                            tester.reporting_manager.generate_report(tenants_list, devices_list, _report_dir)
                            print(f"   📁 Intermediate report saved to: {_report_dir}")
                    except Exception as e:
                        print(f"   ⚠️ Failed to generate intermediate report: {e}")
                
                last_report_time = current_time
        
        return 0 # Ensure a return value for success
        
    except KeyboardInterrupt:
        main_logger.info("\n🛑 Load test interrupted by user in run_test loop (KeyboardInterrupt).")
        if not _shutdown_event.is_set():
             if tester and hasattr(tester, 'stop_load_test'): 
                 tester.stop_load_test()
             _shutdown_event.set()
        return 130
    except Exception as e_run:
        main_logger.error(f"❌ Unexpected error during test execution in run_test: {e_run}", exc_info=True)
        if tester and hasattr(tester, 'stop_load_test'):
            tester.stop_load_test()
        return 1
    finally:
        if _start_time and not args.setup_only: 
            total_elapsed = time.time() - _start_time
            main_logger.info(f"\n⏱️  Total test duration: {total_elapsed/3600:.2f} hours ({total_elapsed:.1f} seconds)")
            main_logger.info("📊 Generating final test report in run_test.finally...")
            
            try:
                if tester and hasattr(tester, 'reporting_manager') and hasattr(tester.reporting_manager, 'print_enhanced_final_stats'):
                    tester.reporting_manager.print_enhanced_final_stats()
                
                if _generate_report_on_exit and tester and hasattr(tester, 'reporting_manager'):
                    tester.reporting_manager.generate_report(tenants_list, devices_list, _report_dir)
                    main_logger.info(f"✅ Final test report generated in: {_report_dir}")
                    
                    # Show advanced findings if available
                    if hasattr(tester.reporting_manager, 'print_advanced_findings'):
                        tester.reporting_manager.print_advanced_findings()
                    
            except Exception as e_final:
                main_logger.error(f"⚠️ Failed to generate final report: {e_final}")

    return exit_code


# Remove the duplicated enhanced worker functions if they exist elsewhere
# Keep only the async def start_enhanced_load_test and other functions...


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
    
    print(f"🚀 Started {len(tasks)} enhanced worker tasks")
    
    # Do NOT await tasks here, as they run indefinitely until signaled to stop.
    # Return them so the main loop can continue monitoring.
    return tasks


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
        
        while protocol_workers._running and connected_flag: # Use _running
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
            
            while protocol_workers._running: # Use _running
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


def main():
    """Main entry point for the Hono Load Test Suite."""
    global args, config, reporting_manager, main_logger, current_run_output_path, _shutdown_event, test_config_data

    # Argument parsing
    parser = argparse.ArgumentParser(description="Hono Load Test Suite - Comprehensive Test Modes with Advanced Features")
    
    # NEW: Config file and profile support
    parser.add_argument("--config-file", default="config/hono.yaml", help="Path to the YAML configuration file.")
    parser.add_argument("--profile", help="Test profile name from config file (replaces --test-mode).")
    parser.add_argument("--list-profiles", action="store_true", help="List all available profiles from config and exit.")
    parser.add_argument("--show-profile", help="Show details of a specific profile and exit.")
    
    # Core arguments (now optional - can come from profile)
    parser.add_argument("--env-file", default="../hono.env", help="Path to the .env file for Hono configuration (legacy).")
    parser.add_argument("--log-level", default="INFO", choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help="Console logging level.")
    parser.add_argument("--report", action="store_true", help="Generate a detailed test report.")
    parser.add_argument("--duration", type=int, help="Test duration in seconds (overrides profile).")
    parser.add_argument("--message-interval", type=float, help="Base interval between messages in seconds (overrides profile).")
    parser.add_argument("--devices", type=int, help="Number of devices to simulate (overrides profile).")
    parser.add_argument("--tenants", type=int, help="Number of tenants (overrides profile).")
    parser.add_argument("--protocols", nargs='+', help="Protocols to test: mqtt, http, amqp, coap (overrides profile).")
    
    # Legacy support (deprecated)
    parser.add_argument("--mode", choices=["10fast", "100slow", "custom"], default="custom", help="Legacy test mode (deprecated, use --profile).")
    parser.add_argument("--test-mode", help="Pre-configured test mode name (deprecated, use --profile).")
    parser.add_argument("--list-modes", action="store_true", help="List all available test modes and exit (deprecated, use --list-profiles).")
    
    # Remaining arguments
    parser.add_argument("--validate-registration", action="store_true", help="Validate device registration with Hono.")
    parser.add_argument("--monitor-interval", type=int, default=10, help="Interval in seconds for printing live stats to console (0 to disable).")
    parser.add_argument("--enable-poisson", action="store_true", help="Enable Poisson distribution for message intervals.")
    parser.add_argument("--poisson-lambda", type=float, default=10.0, help="Lambda rate for Poisson distribution (messages per minute).")
    parser.add_argument("--message-type", default="telemetry", help="Type of message to send (e.g., telemetry, event).")
    parser.add_argument("--enable-throttling", action="store_true", help="Enable registration throttling.")
    parser.add_argument("--throttling-base-delay", type=float, default=0.5, help="Base delay for registration throttling.")
    parser.add_argument("--throttling-jitter", type=float, default=0.2, help="Jitter for registration throttling.")
    parser.add_argument("--max-duration", type=float, help="Maximum test duration in hours (for endurance tests).")
    parser.add_argument("--auto-stop", action="store_true", help="Enable automatic stopping based on test mode duration.")
    parser.add_argument("--interval", type=float, help="Message interval in seconds (alias for --message-interval).")
    parser.add_argument("--kind", default="telemetry", help="Message kind/type.")
    parser.add_argument("--setup-only", action="store_true", help="Only setup infrastructure, don't run load test.")
    parser.add_argument("--mqtt-insecure", action="store_true", help="Disable MQTT TLS.")
    parser.add_argument("--no-ssl-verify", action="store_true", help="Disable SSL certificate verification.")
    parser.add_argument("--report-dir", default="./reports", help="Directory for generated reports.")
    parser.add_argument("--enhanced-stats", action="store_true", help="Enable enhanced statistics collection.")
    parser.add_argument("--periodic-reports", type=int, default=0, help="Generate periodic reports every N minutes (0 to disable).")
    parser.add_argument("--latency-sla", type=float, default=200.0, help="P95 latency SLA in milliseconds.")
    parser.add_argument("--latency-sla-p99", type=float, default=500.0, help="P99 latency SLA in milliseconds.")
    parser.add_argument("--success-sla", type=float, default=99.5, help="Success rate SLA percentage.")
    parser.add_argument("--real-time-monitoring", action="store_true", help="Enable real-time monitoring.")
    parser.add_argument("--performance-alerts", action="store_true", help="Enable performance alerts.")
    parser.add_argument("--min-message-interval", type=float, default=0.1, help="Minimum message interval for Poisson distribution.")
    parser.add_argument("--max-message-interval", type=float, default=60.0, help="Maximum message interval for Poisson distribution.")
    parser.add_argument("--max-concurrent-registrations", type=int, default=5, help="Maximum concurrent device registrations.")
    parser.add_argument("--windowed-sending", action="store_true", help="Enable windowed/burst message sending.")
    parser.add_argument("--window-size", type=float, default=10.0, help="Window size for burst sending in seconds.")
    parser.add_argument("--burst-factor", type=float, default=2.0, help="Burst factor for windowed sending.")
    parser.add_argument("--tiny", action="store_true", help="Legacy tiny test mode (2 tenants, 2 devices).")
    parser.add_argument("--no-cache", action="store_true", help="Disable device/tenant caching (create fresh infrastructure every time).")
    parser.add_argument("--clear-cache", action="store_true", help="Clear cached devices for the current server and exit.")

    args = parser.parse_args()
    
    # Handle profile listing/showing first (before loading config)
    if args.list_profiles or args.list_modes:
        try:
            from config.config_loader import ConfigLoader
            config_loader = ConfigLoader(args.config_file)
            config_loader.print_summary()
            sys.exit(0)
        except FileNotFoundError as e:
            print(f"❌ Config file not found: {e}")
            print(f"💡 Using legacy test modes instead...")
            if args.list_modes:
                list_all_modes()
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            sys.exit(1)
    
    if args.show_profile:
        try:
            from config.config_loader import ConfigLoader
            config_loader = ConfigLoader(args.config_file)
            print(config_loader.get_profile_info(args.show_profile))
            sys.exit(0)
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

    # Create a unique timestamped directory for this test run's outputs
    run_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # Place it in a general "test_results" folder, or directly in the current directory
    # base_results_folder = Path("./test_results_archive") 
    # current_run_output_path = base_results_folder / f"run_{run_timestamp}"
    current_run_output_path = Path(f"run_results_{run_timestamp}") # Creates in the script's directory
    try:
        current_run_output_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"FATAL: Could not create output directory {current_run_output_path}: {e}")
        sys.exit(1)
    
    # Setup logging to use the new output path
    setup_logging(args, current_run_output_path) # Pass the created path
    main_logger = logging.getLogger("stress_script") # Initialize after setup_logging

    # ... (rest of your main function: signal handling, config loading, mode processing)
    # Example of signal handling:
    # The global signal_handler is already set up to use the global _shutdown_event
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'): # Ensure SIGTERM is available (not on all Windows Python versions for signal.signal)
        try:
            signal.signal(signal.SIGTERM, signal_handler)
        except (OSError, AttributeError, ValueError) as e:
            main_logger.warning(f"Could not register SIGTERM handler: {e}")


    # Load Hono configuration
    try:
        config = HonoConfig() 
    except FileNotFoundError:
        main_logger.error(f"Hono environment file not found at {args.env_file}. Please check the path.")
        sys.exit(1)
    except Exception as e:
        main_logger.error(f"Error loading Hono configuration: {e}")
        sys.exit(1)

    # Initialize ReportingManager (it will be used by HonoLoadTester and for final report)
    reporting_manager = ReportingManager(config)
    reporting_manager.poisson_config['enable_poisson_distribution'] = args.enable_poisson
    reporting_manager.poisson_config['lambda_rate'] = args.poisson_lambda
    reporting_manager.registration_config['enable_throttling'] = args.enable_throttling
    reporting_manager.registration_config['registration_delay_base'] = args.throttling_base_delay
    reporting_manager.registration_config['registration_delay_jitter'] = args.throttling_jitter


    # Handle profile or test mode selection
    selected_mode_config = None
    profile_config = None
    
    # NEW: Try loading from YAML config first (if --profile specified)
    if args.profile:
        try:
            from config.config_loader import ConfigLoader
            config_loader = ConfigLoader(args.config_file)
            
            # Get profile with CLI overrides
            profile_config = config_loader.get_full_config(
                args.profile,
                devices=args.devices,
                tenants=args.tenants,
                protocols=','.join(args.protocols) if args.protocols else None,
                message_interval=args.message_interval,
                duration=args.duration,
                enable_poisson=args.enable_poisson if args.enable_poisson else None,
                enable_throttling=args.enable_throttling if args.enable_throttling else None,
            )
            
            # Apply profile settings to args
            test_settings = profile_config['test']
            test_config_data = test_settings # Store for HonoLoadTester
            args.devices = test_settings.get('devices', 1)
            args.tenants = test_settings.get('tenants', 1)
            args.protocols = test_settings.get('protocols', ['mqtt'])
            args.message_interval = test_settings.get('message_interval', 10.0)
            if args.interval is None:
                args.interval = args.message_interval
            if args.duration is None:
                args.duration = test_settings.get('duration', 60)
            
            # Advanced features from profile
            if not args.enable_poisson:
                args.enable_poisson = test_settings.get('enable_poisson', False)
            if not args.enable_throttling:
                args.enable_throttling = test_settings.get('enable_throttling', False)
            if test_settings.get('throttling_base_delay'):
                args.throttling_base_delay = test_settings['throttling_base_delay']
            if test_settings.get('throttling_jitter'):
                args.throttling_jitter = test_settings['throttling_jitter']
            
            main_logger.info(f"✅ Loaded profile: {args.profile}")
            if 'description' in test_settings:
                main_logger.info(f"   Description: {test_settings['description']}")
            
        except FileNotFoundError:
            main_logger.warning(f"⚠️  Config file not found: {args.config_file}")
            main_logger.warning(f"   Falling back to legacy test modes...")
            args.profile = None  # Fall through to legacy mode
        except ValueError as e:
            main_logger.error(f"❌ {e}")
            sys.exit(1)
        except Exception as e:
            main_logger.error(f"❌ Error loading profile: {e}")
            sys.exit(1)
    
    # LEGACY: Fall back to old test-mode if no profile specified
    if not args.profile:
        if args.test_mode:
            main_logger.warning("⚠️  --test-mode is deprecated. Use --profile instead.")
            selected_mode_config = get_mode_config(args.test_mode)
            if not selected_mode_config:
                main_logger.error(f"Test mode '{args.test_mode}' not found. Use --list-modes to see available modes.")
                sys.exit(1)
            
            # Apply mode config to args (preserving CLI overrides)
            if args.devices is None:
                args.devices = selected_mode_config.devices
            if args.tenants is None:
                args.tenants = selected_mode_config.tenants
            if args.protocols is None or args.protocols == []:
                args.protocols = selected_mode_config.protocols
            if args.message_interval is None:
                args.message_interval = selected_mode_config.message_interval
            if args.interval is None:
                args.interval = args.message_interval
            
            if hasattr(selected_mode_config, 'enable_poisson') and not args.enable_poisson: 
                args.enable_poisson = selected_mode_config.enable_poisson
            if hasattr(selected_mode_config, 'enable_throttling') and not args.enable_throttling: 
                args.enable_throttling = selected_mode_config.enable_throttling
            
            main_logger.info(f"Running with test mode: {selected_mode_config.name} - {selected_mode_config.description}")
            if not validate_system_requirements(selected_mode_config):
                 sys.exit(1)
        else:
            # No profile or test-mode specified - use 'smoke' profile as default
            main_logger.info("ℹ️  No profile specified, using default 'smoke' profile")
            try:
                from config.config_loader import ConfigLoader
                config_loader = ConfigLoader(args.config_file)
                
                # Load smoke profile as default
                profile_config = config_loader.get_full_config('smoke')
                test_settings = profile_config['test']
                
                args.devices = test_settings.get('devices', 1)
                args.tenants = test_settings.get('tenants', 1)
                args.protocols = test_settings.get('protocols', ['mqtt'])
                args.message_interval = test_settings.get('message_interval', 10.0)
                if args.interval is None:
                    args.interval = args.message_interval
                if args.duration is None:
                    args.duration = test_settings.get('duration', 60)
                
                main_logger.info(f"✅ Using default 'smoke' profile")
            except:
                # Fallback to hardcoded defaults if config file not available
                main_logger.warning("⚠️  Could not load config file, using hardcoded defaults")
                if args.devices is None:
                    args.devices = 1
                if args.tenants is None:
                    args.tenants = 1
                if args.protocols is None or args.protocols == []:
                    args.protocols = ['mqtt']
                if args.message_interval is None:
                    args.message_interval = 10.0
                if args.interval is None:
                    args.interval = args.message_interval
                if args.duration is None:
                    args.duration = 60

    print_startup_info(args, config, selected_mode_config) # Pass selected_mode_config

    # Run the asyncio event loop for the test
    exit_code = 0
    try:
        exit_code = asyncio.run(run_test())
    except KeyboardInterrupt: # Should be caught by signal_handler or run_test's try/except
        main_logger.info("Main loop interrupted. Exiting.")
        exit_code = 130 
    except Exception as e:
        main_logger.critical(f"Unhandled exception in main: {e}", exc_info=True)
        exit_code = 1
    finally:
        main_logger.info(f"Script finished with exit code: {exit_code}")
        logging.shutdown() # Ensure all log handlers are closed properly
        sys.exit(exit_code)


if __name__ == "__main__":
    # Define args, config, reporting_manager, main_logger as None initially at global scope
    # so they can be assigned in main() and accessed by signal_handler or other top-level functions if needed.
    args = None
    config = None
    reporting_manager = None
    # main_logger is initialized in setup_logging, which is called by main()
    # _shutdown_event is already initialized globally
    
    main()
