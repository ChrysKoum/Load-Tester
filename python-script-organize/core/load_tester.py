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
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.infrastructure_manager = InfrastructureManager(config)
        self.reporting_manager = ReportingManager(config)
        
        # Create protocol workers with shared stats
        self.protocol_workers = ProtocolWorkers(
            config, 
            self.reporting_manager.stats, 
            self.reporting_manager.protocol_stats
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
        
        # Initialize test
        self.reporting_manager.initialize_test(protocols)
        self.reporting_manager.set_running(True)
        self.protocol_workers.set_running(True)
        
        workers = []
        
        # Distribute devices across protocols
        devices_per_protocol = len(self.devices) // len(protocols)
        device_index = 0
        
        for protocol in protocols:
            protocol_devices = self.devices[device_index:device_index + devices_per_protocol]
            device_index += devices_per_protocol
            
            for device in protocol_devices:
                if protocol.lower() == "mqtt":
                    worker = threading.Thread(
                        target=self.protocol_workers.mqtt_telemetry_worker,
                        args=(device, message_interval, message_type)
                    )
                elif protocol.lower() == "http":
                    worker = threading.Thread(
                        target=lambda d=device: asyncio.run(
                            self.protocol_workers.http_telemetry_worker(d, message_interval, message_type)
                        )
                    )
                else:
                    self.logger.warning(f"Protocol {protocol} not implemented yet")
                    continue
                
                workers.append(worker)
                worker.start()
        
        # Handle remaining devices with the first protocol
        if device_index < len(self.devices):
            remaining_devices = self.devices[device_index:]
            for device in remaining_devices:
                if protocols[0].lower() == "mqtt":
                    worker = threading.Thread(
                        target=self.protocol_workers.mqtt_telemetry_worker,
                        args=(device, message_interval, message_type)
                    )
                else:
                    worker = threading.Thread(
                        target=lambda d=device: asyncio.run(
                            self.protocol_workers.http_telemetry_worker(d, message_interval, message_type)
                        )
                    )
                workers.append(worker)
                worker.start()
        
        try:
            # Monitor stats
            self.reporting_manager.monitor_stats()
              # Wait for user to stop
            input("\nPress Enter to stop the load test...\n")
            
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        finally:
            self.logger.info("Stopping load test...")
            self.reporting_manager.set_running(False)
            self.protocol_workers.set_running(False)
            
            # Wait for all workers to finish
            for worker in workers:
                worker.join(timeout=5)
            
            self.reporting_manager.print_final_stats()
    
    def generate_report(self, report_dir: str = "./reports"):
        """Generate detailed test report with charts."""
        self.reporting_manager.generate_report(self.tenants, self.devices, report_dir)
    
    def stop_load_test(self):
        """Stop the load testing gracefully."""
        self.logger.info("Stopping load test...")
        self.reporting_manager.set_running(False)
        self.protocol_workers.set_running(False)
