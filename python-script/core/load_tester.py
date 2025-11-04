"""
Main load tester module for Hono Load Test Suite.
Orchestrates the entire load testing process.
"""

import asyncio
import threading
import logging
from typing import List, Optional # Add Optional

from config.hono_config import HonoConfig, load_config_from_env
from models.device import Device
from core.infrastructure import InfrastructureManager
from core.workers import ProtocolWorkers
from core.reporting import ReportingManager # Ensure ReportingManager is imported


class HonoLoadTester:
    """Main class for Hono load testing."""

    def __init__(self, config: HonoConfig, devices: List[Device], tenants: List[str], reporting_manager: Optional[ReportingManager] = None, use_cache: bool = True):
        self.config = config
        self.devices = devices
        self.tenants = tenants
        self.logger = logging.getLogger(__name__)
        self._worker_threads: List[threading.Thread] = []

        if reporting_manager:
            self.reporting_manager = reporting_manager
        else:
            # This case should ideally not happen if stress.py always provides one.
            self.logger.warning("HonoLoadTester creating its own ReportingManager instance. Statistics might be incorrect.")
            self.reporting_manager = ReportingManager(config)

        # Initialize components, ensuring they use the shared reporting_manager
        # Assuming InfrastructureManager and ProtocolWorkers constructors are updated to accept ReportingManager
        self.infrastructure_manager = InfrastructureManager(config, self.reporting_manager, use_cache=use_cache)

        self.protocol_workers = ProtocolWorkers(
            config,
            self.reporting_manager # Pass the whole manager
        )
        # Remove the basicConfig call if logging is fully handled by stress.py's setup_logging
        # logging.basicConfig(
        #     level=logging.INFO,
        #     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        # )
        
    async def load_config_from_env(self, env_file: str = "hono.env"):
        """Load configuration from environment file."""
        await load_config_from_env(self.config, env_file)
    
    async def setup_infrastructure(self, num_tenants: int = 5, num_devices: int = 10):
        """Set up tenants and devices for load testing."""
        tenants, devices, success = await self.infrastructure_manager.setup_infrastructure(num_tenants, num_devices)
        
        self.tenants = tenants
        self.devices = devices
        
        # Update reporting stats from infrastructure manager
        self.reporting_manager.stats.update(self.infrastructure_manager.stats)
        
        return success
    
    def start_load_test(self, protocols: List[str], message_interval: float, message_type: str = "telemetry"):
        """Start the load testing with specified protocols."""
        if not self.devices:
            self.logger.error("No devices available for load testing!")
            return
        
        self.logger.info(f"Starting load test with {len(self.devices)} devices using protocols: {protocols}")
        self.logger.info(f"Message interval: {message_interval}s, Type: {message_type}")
        
        self.reporting_manager.initialize_test(protocols)
        self.reporting_manager.set_running(True)
        self.protocol_workers.set_running(True)
        self.reporting_manager.monitor_stats()

        self._worker_threads.clear() 
        
        # Distribute devices across protocols
        effective_protocols = protocols if protocols else ["mqtt"]
        num_total_devices = len(self.devices)
        num_protocols = len(effective_protocols)

        device_idx_start = 0
        for i, protocol_name in enumerate(effective_protocols):
            # Distribute devices as evenly as possible
            num_devices_for_protocol = num_total_devices // num_protocols
            if i < num_total_devices % num_protocols:
                num_devices_for_protocol += 1
            
            current_protocol_devices = self.devices[device_idx_start : device_idx_start + num_devices_for_protocol]
            device_idx_start += num_devices_for_protocol

            if not current_protocol_devices and num_total_devices > 0:
                 self.logger.warning(f"No devices assigned to protocol {protocol_name} due to distribution logic.")
                 continue
            
            self.logger.info(f"Assigning {len(current_protocol_devices)} devices to protocol {protocol_name}")
            
            # Set device count correctly - this is the ONLY place where device count is set
            if protocol_name in self.reporting_manager.protocol_stats:
                 self.reporting_manager.protocol_stats[protocol_name]['devices'] = len(current_protocol_devices)
                 self.logger.debug(f"Set device count for {protocol_name}: {len(current_protocol_devices)}")

            for device in current_protocol_devices:
                if protocol_name.lower() == "mqtt":
                    thread_target = self.protocol_workers.mqtt_telemetry_worker
                    thread_args = (device, message_interval, message_type)
                    worker_thread = threading.Thread(target=thread_target, args=thread_args)
                    self._worker_threads.append(worker_thread)
                    
                elif protocol_name.lower() == "http":
                    # Fix: Use a proper wrapper function for async HTTP worker
                    def http_worker_wrapper(device_ref, interval, msg_type):
                        asyncio.run(self.protocol_workers.http_telemetry_worker(device_ref, interval, msg_type))
                    
                    worker_thread = threading.Thread(
                        target=http_worker_wrapper, 
                        args=(device, message_interval, message_type)
                    )
                    self._worker_threads.append(worker_thread)
                else:
                    self.logger.warning(f"Protocol {protocol_name} not implemented yet")
                    continue

        # Start all worker threads
        for thread in self._worker_threads:
            thread.start()
        
        self.logger.info(f"{len(self._worker_threads)} worker threads started.")

    async def start_enhanced_load_test(self, protocols: List[str], message_interval: float, args):
        """Start an enhanced load testing with specified protocols and advanced options."""
        if not self.devices:
            self.logger.error("No devices available for load testing!")
            return
        
        self.logger.info(f"Starting enhanced load test with {len(self.devices)} devices using protocols: {protocols}")
        self.logger.info(f"Message interval: {message_interval}s, Args: {args}")
        
        # Initialize or update protocol_stats with device counts
        if self.reporting_manager:
            # Clear previous stats if any, or ensure structure exists
            if 'protocol_stats' not in self.reporting_manager.performance_metrics:
                self.reporting_manager.performance_metrics['protocol_stats'] = {}

            for proto_name in protocols:
                if proto_name not in self.reporting_manager.performance_metrics['protocol_stats']:
                    self.reporting_manager.performance_metrics['protocol_stats'][proto_name] = {
                        'messages_sent': 0,
                        'messages_failed': 0,
                        'response_times': [],
                        'devices': 0 # Initialize if not present
                    }
                # This assumes all devices are used for all specified protocols in this enhanced test.
                # If devices are split, this logic needs to be more granular.
            
            # Correct place to update is when workers are created and assigned devices.
            # Let's assume self.protocol_workers is populated correctly.
            
            # If you have a structure like self.protocol_workers[protocol_name] = list_of_worker_instances
            # And each worker instance knows its device.
            
            # For now, a simpler update based on total devices if only one protocol:
            if len(protocols) == 1:
                 proto_name = protocols[0]
                 if proto_name in self.reporting_manager.performance_metrics['protocol_stats']:
                    self.reporting_manager.performance_metrics['protocol_stats'][proto_name]['devices'] = len(self.devices)
            else:
                # If multiple protocols, you need a way to know how many devices are on each.
                # For now, we'll log a warning if this isn't clear.
                self.logger.warning("Multiple protocols selected; device count per protocol in report might be inaccurate unless explicitly set.")

        self.reporting_manager.initialize_test(protocols)
        self.reporting_manager.set_running(True)
        self.protocol_workers.set_running(True)
        self.reporting_manager.monitor_stats()

        self._worker_threads.clear() 
        
        # Distribute devices across protocols
        effective_protocols = protocols if protocols else ["mqtt"]
        num_total_devices = len(self.devices)
        num_protocols = len(effective_protocols)

        device_idx_start = 0
        for i, protocol_name in enumerate(effective_protocols):
            # Distribute devices as evenly as possible
            num_devices_for_protocol = num_total_devices // num_protocols
            if i < num_total_devices % num_protocols:
                num_devices_for_protocol += 1
            
            current_protocol_devices = self.devices[device_idx_start : device_idx_start + num_devices_for_protocol]
            device_idx_start += num_devices_for_protocol

            if not current_protocol_devices and num_total_devices > 0:
                 self.logger.warning(f"No devices assigned to protocol {protocol_name} due to distribution logic.")
                 continue
            
            self.logger.info(f"Assigning {len(current_protocol_devices)} devices to protocol {protocol_name}")
            
            # Set device count correctly - this is the ONLY place where device count is set
            if protocol_name in self.reporting_manager.protocol_stats:
                 self.reporting_manager.protocol_stats[protocol_name]['devices'] = len(current_protocol_devices)
                 self.logger.debug(f"Set device count for {protocol_name}: {len(current_protocol_devices)}")

            for device in current_protocol_devices:
                if protocol_name.lower() == "mqtt":
                    thread_target = self.protocol_workers.mqtt_telemetry_worker
                    thread_args = (device, message_interval, args.get("message_type", "telemetry"))
                    worker_thread = threading.Thread(target=thread_target, args=thread_args)
                    self._worker_threads.append(worker_thread)
                    
                elif protocol_name.lower() == "http":
                    # Fix: Use a proper wrapper function for async HTTP worker
                    def http_worker_wrapper(device_ref, interval, msg_type):
                        asyncio.run(self.protocol_workers.http_telemetry_worker(device_ref, interval, msg_type))
                    
                    worker_thread = threading.Thread(
                        target=http_worker_wrapper, 
                        args=(device, message_interval, args.get("message_type", "telemetry"))
                    )
                    self._worker_threads.append(worker_thread)
                else:
                    self.logger.warning(f"Protocol {protocol_name} not implemented yet")
                    continue

        # Start all worker threads
        for thread in self._worker_threads:
            thread.start()
        
        self.logger.info(f"🚀 Started {len(self._worker_threads)} enhanced worker tasks")

    def generate_report(self, report_dir: str = "./reports"):
        """Generate detailed test report with charts."""
        self.reporting_manager.generate_report(self.tenants, self.devices, report_dir)
    
    def stop_load_test(self):
        """Stop the load testing gracefully."""
        self.logger.info("Stopping load test execution...")
        self.reporting_manager.set_running(False)
        self.protocol_workers.set_running(False)

        self.logger.info(f"Waiting for {len(self._worker_threads)} worker threads to join...")
        for thread in self._worker_threads:
            thread.join(timeout=10) 
            if thread.is_alive():
                self.logger.warning(f"Thread {thread.name} did not join in time.")
        
        self.logger.info("All worker threads processed.")
        self.reporting_manager.print_final_stats()
