#!/usr/bin/env python3
"""
Docker Service Entry Point - Load Generator
Uses the modular HonoLoadTester to generate load with multiple protocols.
"""

import os
import sys
import json
import asyncio
import logging
import time
import threading
from pathlib import Path

# Add the working code to Python path
sys.path.insert(0, '/app')

from config.hono_config import HonoConfig
from core.load_tester import HonoLoadTester
from models.device import Device


class DockerLoadGenService:
    """Docker service wrapper for load generation."""
    
    def __init__(self):
        # Setup logging
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - LOADGEN - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.config = HonoConfig.from_env()
        
        # Get load generation parameters from environment
        self.protocols = os.getenv('PROTOCOLS', 'mqtt').split(',')
        self.protocols = [p.strip().lower() for p in self.protocols]
        
        self.message_type = os.getenv('MESSAGE_TYPE', 'telemetry')
        self.message_interval = float(os.getenv('MESSAGE_INTERVAL', '10'))
        
        # Shared data directory
        self.shared_dir = Path('/app/shared')
        
        self.logger.info(f"Load generator configured:")
        self.logger.info(f"  Protocols: {self.protocols}")
        self.logger.info(f"  Message type: {self.message_type}")
        self.logger.info(f"  Message interval: {self.message_interval}s")
        
    async def wait_for_validation(self, timeout=300):
        """Wait for validator service to complete."""
        start_time = time.time()
        status_file = self.shared_dir / 'status.json'
        
        while time.time() - start_time < timeout:
            if status_file.exists():
                try:
                    with open(status_file, 'r') as f:
                        status = json.load(f)
                    
                    if status.get('validator_completed'):
                        self.logger.info("Validator service completed")
                        return True
                    elif status.get('validation_error'):
                        self.logger.warning(f"Validator service failed: {status['validation_error']}")
                        # Continue anyway - we might still be able to run load tests
                        return True
                        
                except Exception as e:
                    self.logger.warning(f"Could not read status file: {e}")
            
            self.logger.info("Waiting for validator service to complete...")
            await asyncio.sleep(10)
        
        self.logger.warning("Timeout waiting for validator service, proceeding anyway")
        return True
        
    async def load_devices(self):
        """Load devices from shared storage."""
        devices_file = self.shared_dir / 'devices.json'
        
        if not devices_file.exists():
            raise FileNotFoundError("Devices file not found. Registrar may have failed.")
        
        with open(devices_file, 'r') as f:
            devices_data = json.load(f)
        
        devices = []
        for device_data in devices_data:
            device = Device(
                device_id=device_data['device_id'],
                tenant_id=device_data['tenant_id'],
                auth_id=device_data['auth_id'],
                password=device_data['password'],
                created_at=device_data['created_at']
            )
            devices.append(device)
        
        self.logger.info(f"Loaded {len(devices)} devices for load testing")
        return devices
        
    async def run_load_test(self):
        """Run the load test using the modular load tester."""
        try:
            # Wait for validation to complete
            await self.wait_for_validation()
            
            # Load devices
            devices = await self.load_devices()
            
            if not devices:
                raise Exception("No devices available for load testing")
            
            # Create load tester and override the interactive behavior
            load_tester = HonoLoadTester(self.config)
            
            # Set up the load tester with our devices
            load_tester.devices = devices
            
            self.logger.info(f"Starting load test with {len(devices)} devices")
            self.logger.info(f"Using protocols: {', '.join(self.protocols)}")
            
            # Start load test without interactive input
            load_tester.reporting_manager.initialize_test(self.protocols)
            load_tester.reporting_manager.set_running(True)
            load_tester.protocol_workers.set_running(True)
            
            workers = []
            
            # Distribute devices across protocols
            devices_per_protocol = len(devices) // len(self.protocols)
            device_index = 0
            
            for protocol in self.protocols:
                protocol_devices = devices[device_index:device_index + devices_per_protocol]
                device_index += devices_per_protocol
                
                for device in protocol_devices:
                    if protocol.lower() == "mqtt":
                        worker = threading.Thread(
                            target=load_tester.protocol_workers.mqtt_telemetry_worker,
                            args=(device, self.message_interval, self.message_type)
                        )
                    elif protocol.lower() == "http":
                        worker = threading.Thread(
                            target=lambda d=device: asyncio.run(
                                load_tester.protocol_workers.http_telemetry_worker(d, self.message_interval, self.message_type)
                            )
                        )
                    else:
                        self.logger.warning(f"Protocol {protocol} not implemented yet")
                        continue
                    
                    workers.append(worker)
                    worker.start()
            
            # Handle remaining devices with the first protocol
            if device_index < len(devices):
                remaining_devices = devices[device_index:]
                for device in remaining_devices:
                    if self.protocols[0].lower() == "mqtt":
                        worker = threading.Thread(
                            target=load_tester.protocol_workers.mqtt_telemetry_worker,
                            args=(device, self.message_interval, self.message_type)
                        )
                    else:
                        worker = threading.Thread(
                            target=lambda d=device: asyncio.run(
                                load_tester.protocol_workers.http_telemetry_worker(d, self.message_interval, self.message_type)
                            )
                        )
                    workers.append(worker)
                    worker.start()
            
            # Start monitoring
            load_tester.reporting_manager.monitor_stats()
            
            self.logger.info("Load test started successfully - running in Docker mode (continuous)")
            
            # Run indefinitely until stopped
            try:
                while True:
                    await asyncio.sleep(60)  # Check every minute
                    if not load_tester.reporting_manager.running:
                        break
            except KeyboardInterrupt:
                self.logger.info("Load test interrupted by user")
            except asyncio.CancelledError:
                self.logger.info("Load test cancelled")
            finally:
                self.logger.info("Stopping load test...")
                load_tester.reporting_manager.set_running(False)
                load_tester.protocol_workers.set_running(False)
                
                # Wait for all workers to finish
                for worker in workers:
                    worker.join(timeout=5)
                
                # Generate final report
                self.logger.info("Generating final load test report...")
                try:
                    load_tester.generate_report()
                except Exception as e:
                    self.logger.warning(f"Could not generate report: {e}")
            
        except Exception as e:
            self.logger.error(f"Load test failed: {e}")
            raise
            
    async def run(self):
        """Main service loop."""
        await self.run_load_test()


def main():
    """Main entry point for Docker load generator service."""
    service = DockerLoadGenService()
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logging.info("Load generator service stopped by user")
    except Exception as e:
        logging.error(f"Load generator service failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
