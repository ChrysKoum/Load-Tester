#!/usr/bin/env python3
"""
Hono Load Test - Registrar Service
Handles tenant and device registration for the load testing framework.
"""

import os
import sys
import json
import uuid
import time
import asyncio
import aiohttp
import aiofiles
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

@dataclass
class Tenant:
    id: str
    name: str
    created_at: float

@dataclass
class Device:
    id: str
    tenant_id: str
    auth_id: str
    password: str
    created_at: float

class HonoRegistrar:
    """Service for registering tenants and devices with Hono."""
    
    def __init__(self):
        self.tenants: List[Tenant] = []
        self.devices: List[Device] = []
        
        # Setup logging
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - REGISTRAR - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.registry_ip = os.getenv('REGISTRY_IP', 'localhost')
        self.registry_port = int(os.getenv('REGISTRY_PORT', '28443'))
        self.verify_ssl = os.getenv('VERIFY_SSL', 'false').lower() == 'true'
        self.messaging_type = os.getenv('MESSAGING_TYPE', 'kafka')
        
        # Test configuration
        self.tenant_count = int(os.getenv('TENANT_COUNT', '5'))
        self.device_count = int(os.getenv('DEVICE_COUNT', '10'))
        
        self.logger.info(f"Registrar initialized - Tenants: {self.tenant_count}, Devices: {self.device_count}")
        
    async def create_tenant(self, session: aiohttp.ClientSession, tenant_name: str = None) -> Optional[Tenant]:
        """Create a new tenant in Hono."""
        url = f"https://{self.registry_ip}:{self.registry_port}/v1/tenants"
        
        payload = {
            "ext": {
                "messaging-type": self.messaging_type
            }
        }
        
        # Add tenant name if provided
        if tenant_name:
            payload["ext"]["tenant-name"] = tenant_name
        
        headers = {"Content-Type": "application/json"}
        
        try:
            async with session.post(url, json=payload, headers=headers, ssl=self.verify_ssl) as response:
                if response.status == 201:
                    data = await response.json()
                    tenant = Tenant(
                        id=data['id'],
                        name=tenant_name or f"tenant-{data['id'][:8]}",
                        created_at=time.time()
                    )
                    self.logger.info(f"Created tenant: {tenant.id} ({tenant.name})")
                    return tenant
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to create tenant: {response.status} - {error_text}")
                    return None
        except Exception as e:
            self.logger.error(f"Exception creating tenant: {e}")
            return None
    
    async def create_device(self, session: aiohttp.ClientSession, tenant_id: str) -> Optional[Device]:
        """Create a new device in the specified tenant."""
        url = f"https://{self.registry_ip}:{self.registry_port}/v1/devices/{tenant_id}"
        
        try:
            async with session.post(url, ssl=self.verify_ssl) as response:
                if response.status == 201:
                    data = await response.json()
                    device_id = data['id']
                    password = f"pwd-{uuid.uuid4().hex[:12]}"
                    
                    device = Device(
                        id=device_id,
                        tenant_id=tenant_id,
                        auth_id=device_id,  # Using device_id as auth_id
                        password=password,
                        created_at=time.time()
                    )
                    
                    # Set device credentials
                    if await self.set_device_credentials(session, device):
                        self.logger.info(f"Created device: {device.id} in tenant: {tenant_id}")
                        return device
                    else:
                        self.logger.error(f"Failed to set credentials for device: {device.id}")
                        return None
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to create device: {response.status} - {error_text}")
                    return None
        except Exception as e:
            self.logger.error(f"Exception creating device: {e}")
            return None
    
    async def set_device_credentials(self, session: aiohttp.ClientSession, device: Device) -> bool:
        """Set password credentials for a device."""
        url = f"https://{self.registry_ip}:{self.registry_port}/v1/credentials/{device.tenant_id}/{device.id}"
        
        payload = [{
            "type": "hashed-password",
            "auth-id": device.auth_id,
            "secrets": [{
                "pwd-plain": device.password
            }]
        }]
        
        headers = {"Content-Type": "application/json"}
        
        try:
            async with session.put(url, json=payload, headers=headers, ssl=self.verify_ssl) as response:
                if response.status == 204:
                    return True
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to set credentials for {device.id}: {response.status} - {error_text}")
                    return False
        except Exception as e:
            self.logger.error(f"Exception setting credentials for {device.id}: {e}")
            return False
    
    async def register_infrastructure(self):
        """Register all tenants and devices."""
        self.logger.info("Starting infrastructure registration...")
        
        connector = aiohttp.TCPConnector(ssl=self.verify_ssl, limit=50)
        timeout = aiohttp.ClientTimeout(total=60)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Create tenants
            self.logger.info(f"Creating {self.tenant_count} tenants...")
            tenant_tasks = []
            for i in range(self.tenant_count):
                tenant_name = f"loadtest-tenant-{i+1:03d}"
                tenant_tasks.append(self.create_tenant(session, tenant_name))
            
            tenant_results = await asyncio.gather(*tenant_tasks, return_exceptions=True)
            self.tenants = [t for t in tenant_results if isinstance(t, Tenant)]
            
            if len(self.tenants) == 0:
                self.logger.error("No tenants created successfully!")
                return False
            
            self.logger.info(f"Successfully created {len(self.tenants)} tenants")
            
            # Distribute devices evenly across tenants
            devices_per_tenant = self.device_count // len(self.tenants)
            remaining_devices = self.device_count % len(self.tenants)
            
            self.logger.info(f"Creating {self.device_count} devices across {len(self.tenants)} tenants...")
            device_tasks = []
            
            for i, tenant in enumerate(self.tenants):
                tenant_device_count = devices_per_tenant + (1 if i < remaining_devices else 0)
                self.logger.info(f"Creating {tenant_device_count} devices for tenant {tenant.name}")
                
                for _ in range(tenant_device_count):
                    device_tasks.append(self.create_device(session, tenant.id))
            
            device_results = await asyncio.gather(*device_tasks, return_exceptions=True)
            self.devices = [d for d in device_results if isinstance(d, Device)]
            
            if len(self.devices) == 0:
                self.logger.error("No devices created successfully!")
                return False
            
            self.logger.info(f"Successfully created {len(self.devices)} devices")
            
            # Save to shared files
            await self.save_infrastructure_data()
            
            return True
    
    async def save_infrastructure_data(self):
        """Save tenant and device data to shared files."""
        try:
            # Save tenants
            tenants_data = [asdict(tenant) for tenant in self.tenants]
            async with aiofiles.open('/app/shared/tenants.json', 'w') as f:
                await f.write(json.dumps(tenants_data, indent=2))
            
            # Save devices
            devices_data = [asdict(device) for device in self.devices]
            async with aiofiles.open('/app/shared/devices.json', 'w') as f:
                await f.write(json.dumps(devices_data, indent=2))
            
            # Save status
            status = {
                'service': 'registrar',
                'status': 'completed',
                'timestamp': time.time(),
                'tenants_created': len(self.tenants),
                'devices_created': len(self.devices),
                'tenant_count_requested': self.tenant_count,
                'device_count_requested': self.device_count
            }
            async with aiofiles.open('/app/shared/status.json', 'w') as f:
                await f.write(json.dumps(status, indent=2))
            
            self.logger.info("Infrastructure data saved to shared volume")
            
        except Exception as e:
            self.logger.error(f"Failed to save infrastructure data: {e}")
    
    async def wait_for_completion_signal(self):
        """Wait for external signal to complete (for orchestration)."""
        self.logger.info("Registration complete. Waiting for completion signal...")
        
        # In a real orchestration, this might wait for a signal file or HTTP endpoint
        # For now, we'll just wait a bit and then exit
        await asyncio.sleep(10)
        
        self.logger.info("Registrar service completed successfully")

async def main():
    """Main entry point for the registrar service."""
    registrar = HonoRegistrar()
    
    try:
        success = await registrar.register_infrastructure()
        if not success:
            sys.exit(1)
        
        await registrar.wait_for_completion_signal()
        
    except KeyboardInterrupt:
        registrar.logger.info("Registrar service interrupted")
        sys.exit(1)
    except Exception as e:
        registrar.logger.error(f"Registrar service failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
