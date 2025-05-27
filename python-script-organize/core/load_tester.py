"""
Main load tester module for Hono Load Test Suite.
Orchestrates the entire load testing process.
"""

import asyncio
import threading
import logging
from typing import List

from config.hono_config import HonoConfig, load_config_from_env
from models.device import Device
from core.infrastructure import InfrastructureManager
from core.workers import ProtocolWorkers
from core.reporting import ReportingManager


class HonoLoadTester:
    """Main class for Hono load testing."""
    
    def __init__(self, config: HonoConfig):
        self.config = config
        self.tenants: List[str] = []
        self.devices: List[Device] = []
        self._worker_threads: List[threading.Thread] = [] # Store worker threads
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.infrastructure_manager = InfrastructureManager(config)
        self.reporting_manager = ReportingManager(config)
        
        # Create protocol workers with shared stats AND reporting manager
        self.protocol_workers = ProtocolWorkers(
            config, 
            self.reporting_manager.stats, 
            self.reporting_manager.protocol_stats,
            self.reporting_manager  # Pass the reporting manager
        )
    
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
        self.reporting_manager.monitor_stats() # Start the monitoring thread

        self._worker_threads.clear() 
        
        # Distribute devices across protocols
        effective_protocols = protocols if protocols else ["mqtt"] # Default to mqtt if empty
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

            if not current_protocol_devices and num_total_devices > 0 : # If devices exist but none assigned, log warning
                 self.logger.warning(f"No devices assigned to protocol {protocol_name} due to distribution logic.")
                 continue
            
            self.logger.info(f"Assigning {len(current_protocol_devices)} devices to protocol {protocol_name}")
            if protocol_name in self.reporting_manager.protocol_stats:
                 self.reporting_manager.protocol_stats[protocol_name]['devices'] = len(current_protocol_devices)


            for device in current_protocol_devices:
                thread_target = None
                thread_args = () # For non-lambda targets

                if protocol_name.lower() == "mqtt":
                    thread_target = self.protocol_workers.mqtt_telemetry_worker
                    thread_args = (device, message_interval, message_type)
                elif protocol_name.lower() == "http":
                    # Lambda to run async worker, capturing current device, interval, type
                    thread_target = lambda d=device, mi=message_interval, mt=message_type: \
                                    asyncio.run(self.protocol_workers.http_telemetry_worker(d, mi, mt))
                else:
                    self.logger.warning(f"Protocol {protocol_name} not implemented yet")
                    continue
                
                worker_thread = threading.Thread(target=thread_target, args=thread_args)
                self._worker_threads.append(worker_thread)

        # Start all worker threads
        for thread in self._worker_threads:
            thread.start()
        
        self.logger.info(f"{len(self._worker_threads)} worker threads started.")

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
