"""
Infrastructure management module for Hono Load Test Suite.
Handles tenant and device creation, credential management, and validation.
"""

import os
import ssl
import time
import asyncio
import aiohttp
import logging
from typing import List, Optional

from models.device import Device
from config.hono_config import HonoConfig


class InfrastructureManager:
    """Manages Hono infrastructure setup including tenants and devices."""
    
    def __init__(self, config: HonoConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.stats = {
            'tenants_registered': 0,
            'devices_registered': 0,
            'validation_success': 0,
            'validation_failed': 0
        }
    
    async def create_tenant(self, session: aiohttp.ClientSession) -> str:
        """Create a new tenant and return its ID."""
        # Use HTTPS or HTTP based on TLS setting
        protocol_scheme = "https" if self.config.use_tls else "http"
        url = f"{protocol_scheme}://{self.config.registry_ip}:{self.config.registry_port}/v1/tenants"
        
        payload = {
            "ext": {
                "messaging-type": "kafka"
            }
        }
        
        headers = {"Content-Type": "application/json"}
        
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 201:
                    data = await response.json()
                    tenant_id = data['id']
                    self.stats['tenants_registered'] += 1
                    self.logger.info(f"Created tenant: {tenant_id}")
                    return tenant_id
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to create tenant: {response.status} - {error_text}")
                    return None
        except Exception as e:
            self.logger.error(f"Exception creating tenant: {e}")
            return None
    
    async def create_device(self, session: aiohttp.ClientSession, tenant_id: str) -> Optional[Device]:
        """Create a new device in the specified tenant."""
        # Use HTTPS or HTTP based on TLS setting
        protocol_scheme = "https" if self.config.use_tls else "http"
        url = f"{protocol_scheme}://{self.config.registry_ip}:{self.config.registry_port}/v1/devices/{tenant_id}"
        
        try:
            async with session.post(url) as response:
                if response.status == 201:
                    data = await response.json()
                    device_id = data['id']
                    
                    # Use consistent password from config, fallback to environment default
                    password = self.config.my_password if self.config.my_password else "this-is-my-password"
                    
                    device = Device(
                        device_id=device_id,
                        tenant_id=tenant_id,
                        password=password,
                        auth_id=device_id  # Using device_id as auth_id like in registrar
                    )
                    
                    # Set device credentials
                    if await self.set_device_credentials(session, device):
                        self.stats['devices_registered'] += 1
                        self.logger.info(f"Created device: {device_id} in tenant: {tenant_id} with password: {password}")
                        return device
                    else:
                        self.logger.error(f"Failed to set credentials for device: {device_id}")
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
        # Use HTTPS or HTTP based on TLS setting
        protocol_scheme = "https" if self.config.use_tls else "http"
        url = f"{protocol_scheme}://{self.config.registry_ip}:{self.config.registry_port}/v1/credentials/{device.tenant_id}/{device.device_id}"
        
        payload = [{
            "type": "hashed-password",
            "auth-id": device.auth_id,
            "secrets": [{
                "pwd-plain": device.password
            }]
        }]
        
        headers = {"Content-Type": "application/json"}
        
        try:
            async with session.put(url, json=payload, headers=headers) as response:
                if response.status == 204:
                    self.logger.debug(f"Successfully set credentials for device {device.device_id} with password: {device.password}")
                    return True
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to set credentials: {response.status} - {error_text}")
                    return False
        except Exception as e:
            self.logger.error(f"Exception setting credentials: {e}")
            return False
    
    async def validate_device_http(self, session: aiohttp.ClientSession, device: Device) -> bool:
        """Validate device by sending a test telemetry message via HTTP."""
        # Use HTTPS or HTTP based on TLS setting
        protocol_scheme = "https" if self.config.use_tls else "http"
        url = f"{protocol_scheme}://{self.config.http_adapter_ip}:{self.config.http_adapter_port}/telemetry"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        auth = aiohttp.BasicAuth(f"{device.auth_id}@{device.tenant_id}", device.password)
        payload = {
            "validation": True, 
            "timestamp": int(time.time()),
            "device_id": device.device_id,
            "temperature": 25.0,
            "humidity": 60.0,
            "message": "validation_test"
        }
        
        try:
            async with session.post(url, json=payload, headers=headers, auth=auth) as response:
                if 200 <= response.status < 300:
                    self.stats['validation_success'] += 1
                    self.logger.debug(f"Validation successful for device {device.device_id} using password: {device.password}")
                    return True
                else:
                    self.stats['validation_failed'] += 1
                    error_text = await response.text()
                    self.logger.warning(f"Validation failed for device {device.device_id}: {response.status} - {error_text}")
                    return False
        except Exception as e:
            self.stats['validation_failed'] += 1
            self.logger.error(f"Exception validating device {device.device_id}: {e}")
            return False
    
    async def setup_infrastructure(self, num_tenants: int = 5, num_devices: int = 10) -> tuple[List[str], List[Device], bool]:
        """Set up tenants and devices for load testing."""
        self.logger.info(f"Setting up {num_tenants} tenants with {num_devices} devices total...")
        
        # Configure SSL context properly based on environment
        ssl_context = None
        if self.config.use_tls:
            if self.config.ca_file_path and os.path.exists(self.config.ca_file_path):
                ssl_context = ssl.create_default_context(cafile=self.config.ca_file_path)
            else:
                ssl_context = ssl.create_default_context()
            
            if not self.config.verify_ssl:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context, limit=100)
        timeout = aiohttp.ClientTimeout(total=30)
        
        tenants = []
        devices = []
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Create tenants
            tenant_tasks = [self.create_tenant(session) for _ in range(num_tenants)]
            tenant_results = await asyncio.gather(*tenant_tasks, return_exceptions=True)
            
            tenants = [t for t in tenant_results if isinstance(t, str)]
            
            if len(tenants) == 0:
                self.logger.error("No tenants created successfully!")
                return tenants, devices, False
            
            self.logger.info(f"Created {len(tenants)} tenants successfully")
            
            # Distribute devices evenly across tenants
            devices_per_tenant = num_devices // len(tenants)
            remaining_devices = num_devices % len(tenants)
            
            device_tasks = []
            for i, tenant_id in enumerate(tenants):
                tenant_device_count = devices_per_tenant + (1 if i < remaining_devices else 0)
                for _ in range(tenant_device_count):
                    device_tasks.append(self.create_device(session, tenant_id))
            
            device_results = await asyncio.gather(*device_tasks, return_exceptions=True)
            devices = [d for d in device_results if isinstance(d, Device)]
            
            if len(devices) == 0:
                self.logger.error("No devices created successfully!")
                return tenants, devices, False
            
            self.logger.info(f"Created {len(devices)} devices successfully")
            
            # Validate all devices
            self.logger.info("Validating devices with initial telemetry...")
            validation_tasks = [self.validate_device_http(session, device) for device in devices]
            validation_results = await asyncio.gather(*validation_tasks, return_exceptions=True)
            
            successful_validations = sum(1 for r in validation_results if r is True)
            self.logger.info(f"Validation complete: {successful_validations}/{len(devices)} devices validated")
            
            if successful_validations == len(devices):
                self.logger.info("✅ All devices validated successfully! Ready to start load testing.")
                return tenants, devices, True
            else:
                self.logger.warning(f"⚠️  Only {successful_validations}/{len(devices)} devices validated. Some may fail during load testing.")
                return tenants, devices, True
