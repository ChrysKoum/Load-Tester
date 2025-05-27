#!/usr/bin/env python3
"""
Docker Service Entry Point - Registrar
Uses the modular HonoLoadTester infrastructure to register tenants and devices.
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path

# Add the working code to Python path
sys.path.insert(0, '/app')

from config.hono_config import HonoConfig
from core.infrastructure import InfrastructureManager
from utils.constants import DEFAULT_DEVICE_COUNT, DEFAULT_TENANT_COUNT


class DockerRegistrarService:
    """Docker service wrapper for tenant and device registration."""
    
    def __init__(self):
        # Setup logging
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - REGISTRAR - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.config = HonoConfig.from_env()
        self.infrastructure = HonoInfrastructure(self.config)
        
        # Get counts from environment
        self.tenant_count = int(os.getenv('TENANT_COUNT', DEFAULT_TENANT_COUNT))
        self.device_count = int(os.getenv('DEVICE_COUNT', DEFAULT_DEVICE_COUNT))
        
        # Shared data directory
        self.shared_dir = Path('/app/shared')
        self.shared_dir.mkdir(exist_ok=True)
        
    async def register_infrastructure(self):
        """Register tenants and devices, save to shared storage."""
        try:
            self.logger.info(f"Starting registration: {self.tenant_count} tenants, {self.device_count} devices per tenant")
            
            # Register tenants and devices
            tenants, devices = await self.infrastructure.register_tenants_and_devices(
                self.tenant_count, 
                self.device_count
            )
            
            # Save to shared storage for other services
            tenants_file = self.shared_dir / 'tenants.json'
            devices_file = self.shared_dir / 'devices.json'
            status_file = self.shared_dir / 'status.json'
            
            # Convert to serializable format
            tenants_data = [
                {
                    'id': tenant.id,
                    'name': tenant.name,
                    'created_at': tenant.created_at
                }
                for tenant in tenants
            ]
            
            devices_data = [
                {
                    'device_id': device.device_id,
                    'tenant_id': device.tenant_id,
                    'auth_id': device.auth_id,
                    'password': device.password,
                    'created_at': device.created_at
                }
                for device in devices
            ]
            
            # Write data files
            with open(tenants_file, 'w') as f:
                json.dump(tenants_data, f, indent=2)
                
            with open(devices_file, 'w') as f:
                json.dump(devices_data, f, indent=2)
                
            # Write status file
            status = {
                'registrar_completed': True,
                'tenant_count': len(tenants),
                'device_count': len(devices),
                'completed_at': asyncio.get_event_loop().time()
            }
            
            with open(status_file, 'w') as f:
                json.dump(status, f, indent=2)
                
            self.logger.info(f"Registration completed successfully")
            self.logger.info(f"Registered {len(tenants)} tenants and {len(devices)} devices")
            
        except Exception as e:
            self.logger.error(f"Registration failed: {e}")
            # Write error status
            status = {
                'registrar_completed': False,
                'error': str(e),
                'failed_at': asyncio.get_event_loop().time()
            }
            
            status_file = self.shared_dir / 'status.json'
            with open(status_file, 'w') as f:
                json.dump(status, f, indent=2)
            
            raise
            
    async def run(self):
        """Main service loop."""
        await self.register_infrastructure()
        
        # Keep container running to maintain data
        self.logger.info("Registration service completed. Keeping container alive...")
        while True:
            await asyncio.sleep(60)  # Check every minute


def main():
    """Main entry point for Docker registrar service."""
    service = DockerRegistrarService()
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logging.info("Registrar service stopped by user")
    except Exception as e:
        logging.error(f"Registrar service failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
