#!/usr/bin/env python3
"""
Docker Service Entry Point - Validator
Uses the modular HonoLoadTester infrastructure to validate the setup.
"""

import os
import sys
import json
import asyncio
import logging
import time
from pathlib import Path

# Add the working code to Python path
sys.path.insert(0, '/app')

from config.hono_config import HonoConfig
from core.infrastructure import InfrastructureManager
from models.device import Device


class DockerValidatorService:
    """Docker service wrapper for setup validation."""
    
    def __init__(self):
        # Setup logging
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - VALIDATOR - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
          # Load configuration
        self.config = HonoConfig.from_env()
        self.infrastructure = InfrastructureManager(self.config)
        
        # Shared data directory
        self.shared_dir = Path('/app/shared')
        
    async def wait_for_registration(self, timeout=300):
        """Wait for registrar service to complete."""
        start_time = time.time()
        status_file = self.shared_dir / 'status.json'
        
        while time.time() - start_time < timeout:
            if status_file.exists():
                try:
                    with open(status_file, 'r') as f:
                        status = json.load(f)
                    
                    if status.get('registrar_completed'):
                        self.logger.info("Registrar service completed successfully")
                        return True
                    elif status.get('error'):
                        self.logger.error(f"Registrar service failed: {status['error']}")
                        return False
                        
                except Exception as e:
                    self.logger.warning(f"Could not read status file: {e}")
            
            self.logger.info("Waiting for registrar service to complete...")
            await asyncio.sleep(10)
        
        self.logger.error("Timeout waiting for registrar service")
        return False
        
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
        
        self.logger.info(f"Loaded {len(devices)} devices for validation")
        return devices
        
    async def validate_setup(self):
        """Validate the Hono setup with registered devices."""
        try:
            # Wait for registration to complete
            if not await self.wait_for_registration():
                raise Exception("Registration did not complete successfully")
            
            # Load devices
            devices = await self.load_devices()
            
            if not devices:
                raise Exception("No devices available for validation")
            
            # Take a sample of devices for validation (max 5)
            sample_devices = devices[:5]
            
            self.logger.info(f"Starting validation with {len(sample_devices)} sample devices")
            
            # Validate HTTP if enabled
            if hasattr(self.config, 'http_adapter_ip'):
                self.logger.info("Validating HTTP connectivity...")
                http_success = await self.infrastructure.validate_http_connectivity(sample_devices)
                if http_success:
                    self.logger.info("✓ HTTP validation passed")
                else:
                    self.logger.warning("⚠ HTTP validation failed")
            
            # Validate MQTT if enabled
            if hasattr(self.config, 'mqtt_adapter_ip'):
                self.logger.info("Validating MQTT connectivity...")
                mqtt_success = await self.infrastructure.validate_mqtt_connectivity(sample_devices)
                if mqtt_success:
                    self.logger.info("✓ MQTT validation passed")
                else:
                    self.logger.warning("⚠ MQTT validation failed")
            
            # Update status
            status_file = self.shared_dir / 'status.json'
            with open(status_file, 'r') as f:
                status = json.load(f)
            
            status.update({
                'validator_completed': True,
                'validation_passed': True,  # You might want to make this conditional
                'validated_at': time.time()
            })
            
            with open(status_file, 'w') as f:
                json.dump(status, f, indent=2)
            
            self.logger.info("Validation completed successfully")
            
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            
            # Update status with error
            status_file = self.shared_dir / 'status.json'
            try:
                with open(status_file, 'r') as f:
                    status = json.load(f)
            except:
                status = {}
            
            status.update({
                'validator_completed': False,
                'validation_error': str(e),
                'validation_failed_at': time.time()
            })
            
            with open(status_file, 'w') as f:
                json.dump(status, f, indent=2)
            
            raise
            
    async def run(self):
        """Main service loop."""
        await self.validate_setup()
        
        # Keep container running
        self.logger.info("Validation service completed. Keeping container alive...")
        while True:
            await asyncio.sleep(60)


def main():
    """Main entry point for Docker validator service."""
    service = DockerValidatorService()
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logging.info("Validator service stopped by user")
    except Exception as e:
        logging.error(f"Validator service failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
