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
from typing import List, Dict, Optional # Add Optional

from models.device import Device
from config.hono_config import HonoConfig
from core.reporting import ReportingManager # Add this if not present

class InfrastructureManager:
    """Manages Hono infrastructure components like tenants and devices."""
    
    def __init__(self, config: HonoConfig, reporting_manager: Optional[ReportingManager] = None): # Modified
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.tenants: List[str] = []
        self.devices: List[Device] = []
        # Initialize stats dictionary for infrastructure-related metrics
        self.stats = {
            'tenants_created': 0,
            'devices_created': 0,
            'credentials_set': 0,
            'validation_success': 0,
            'validation_failed': 0,
            'registration_attempts': 0,
            'registration_throttled': 0,
            'devices_registered': 0 # Specifically for throttled registration success
        }
        if reporting_manager:
            self.reporting_manager = reporting_manager
        else:
            self.logger.warning("InfrastructureManager creating its own ReportingManager. Validation stats might not be globally tracked.")
            self.reporting_manager = ReportingManager(config) # Fallback

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
                    self.stats['tenants_created'] += 1 # Corrected key here                    self.logger.info(f"Created tenant: {tenant_id}")
                    return tenant_id
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to create tenant: {response.status} - {error_text}")
                    return None
        except Exception as e:
            self.logger.error(f"Exception creating tenant: {e}")
            return None
    
    async def create_device(self, session: aiohttp.ClientSession, tenant_id: str, device_id_suffix: Optional[str] = None) -> Optional[Device]:
        """Create a new device in the specified tenant."""
        device_id = f"device-{device_id_suffix if device_id_suffix else os.urandom(8).hex()}"
        # Use HTTPS or HTTP based on TLS setting
        protocol_scheme = "https" if self.config.use_tls else "http"
        url = f"{protocol_scheme}://{self.config.registry_ip}:{self.config.registry_port}/v1/devices/{tenant_id}/{device_id}"
        
        self.logger.debug(f"Creating device: {url}")
        try:
            headers = {"Content-Type": "application/json"}
            async with session.post(url, headers=headers, json={}) as response: # Empty JSON body
                if response.status == 201:
                    self.logger.info(f"Device {device_id} created in tenant {tenant_id}")
                    # Device object needs password, which is set by set_device_credentials
                    # For now, create a placeholder and set credentials next
                    device_password = f"this-is-my-password" # Placeholder, should be secure
                    device = Device(device_id=device_id, tenant_id=tenant_id, password=device_password, auth_id=device_id)
                    
                    # Set credentials immediately after creation
                    if await self.set_device_credentials(session, device):
                        self.logger.info(f"Credentials set for device {device.device_id}")
                        return device
                    else:
                        self.logger.error(f"Failed to set credentials for device {device.device_id}")
                        # Optionally, attempt to delete the device if credential setting fails
                        # await self.delete_device(session, tenant_id, device_id)
                        return None
                elif response.status == 409: # Conflict, device already exists
                    self.logger.warning(f"Device {device_id} already exists in tenant {tenant_id}. Attempting to retrieve/reuse.")
                    # Try to set/reset credentials for existing device
                    device_password = f"this-is-my-password" # Placeholder
                    device = Device(device_id=device_id, tenant_id=tenant_id, password=device_password, auth_id=device_id)
                    if await self.set_device_credentials(session, device):
                        self.logger.info(f"Credentials reset for existing device {device.device_id}")
                        return device
                    else:
                        self.logger.error(f"Failed to set credentials for existing device {device.device_id}")
                        return None
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to create device {device_id}: {response.status} - {error_text}")
                    return None
        except Exception as e:
            self.logger.error(f"Exception creating device {device_id}: {e}", exc_info=True)
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
    
    """Enhanced infrastructure manager with registration throttling."""
    
    async def setup_infrastructure_with_throttling(self, num_tenants: int = 5, num_devices: int = 10, 
                                                  reporting_manager: Optional['ReportingManager'] = None) -> bool:
        """Set up infrastructure with advanced registration throttling."""
        self.logger.info(f"Setting up {num_tenants} tenants with {num_devices} devices total (throttled)...")
        
        # Configure SSL context properly based on environment
        ssl_context = None
        if self.config.use_tls:
            if self.config.ca_file_path and os.path.exists(self.config.ca_file_path):
                ssl_context = ssl.create_default_context(cafile=self.config.ca_file_path)
                self.logger.info(f"Using CA file for TLS: {self.config.ca_file_path}")
            else:
                ssl_context = ssl.create_default_context()
                self.logger.info("Using default SSL context for TLS.")
            
            if not self.config.verify_ssl:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                self.logger.warning("SSL certificate verification is DISABLED.")
        
        connector = aiohttp.TCPConnector(ssl=ssl_context, limit=self.config.http_connection_limit if hasattr(self.config, 'http_connection_limit') else 100)
        timeout = aiohttp.ClientTimeout(total=self.config.http_timeout)
        
        created_tenants_list: List[str] = []

        try:
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                # Create tenants first
                tenant_tasks = [self.create_tenant(session) for _ in range(num_tenants)]
                tenant_results = await asyncio.gather(*tenant_tasks, return_exceptions=True)
                
                created_tenants_list = [t for t in tenant_results if isinstance(t, str)]
                self.tenants = created_tenants_list # Store created tenant IDs

                if not self.tenants:
                    self.logger.error("No tenants created successfully during throttled setup!")
                    return False
                self.logger.info(f"Successfully created {len(self.tenants)} tenants for throttled setup.")
                self.stats['tenants_created'] = len(self.tenants)

                # Calculate devices per tenant
                if not self.tenants:
                    self.logger.error("Cannot distribute devices as no tenants were created.")
                    return False

                devices_per_tenant = num_devices // len(self.tenants)
                extra_devices = num_devices % len(self.tenants)
                
                # Create device distribution plan
                device_plan = []
                global_device_index = 0
                
                for i, tenant_id in enumerate(self.tenants):
                    tenant_device_count = devices_per_tenant + (1 if i < extra_devices else 0)
                    
                    for device_index_in_tenant in range(tenant_device_count):
                        device_plan.append({
                            'tenant_id': tenant_id,
                            'global_index': global_device_index,
                            'device_id': f"device-{global_device_index:04d}"
                        })
                        global_device_index += 1
                
                # Create devices SEQUENTIALLY with throttling
                successful_devices: List[Device] = []
                
                for i, device_info in enumerate(device_plan):
                    # Calculate throttling delay
                    delay = 0.0
                    if reporting_manager and hasattr(reporting_manager, 'calculate_registration_delay'):
                        delay = reporting_manager.calculate_registration_delay(
                            device_info['global_index'], num_devices
                        )
                    elif hasattr(self.config, 'throttling_base_delay'):
                        delay = self.config.throttling_base_delay + (device_info['global_index'] * 0.01)
                    else:
                        delay = 0.1 * device_info['global_index']
                    
                    # Apply delay BEFORE creating the device (sequential execution)
                    if delay > 0 and i > 0:  # No delay for the first device
                        self.logger.debug(f"Applying registration delay of {delay:.2f}s for device {device_info['device_id']}")
                        await asyncio.sleep(delay)
                    
                    # Create device sequentially
                    try:
                        device_obj = await self.create_device(
                            session, 
                            device_info['tenant_id'], 
                            device_id_suffix=f"{device_info['global_index']:04d}"
                        )
                        
                        if device_obj:
                            successful_devices.append(device_obj)
                            # self.logger.info(f"Device {device_obj.device_id} created in tenant {device_obj.tenant_id}")
                        
                        # Record registration metrics
                        if reporting_manager and hasattr(reporting_manager, 'record_registration_attempt'):
                            reporting_manager.record_registration_attempt(
                                device_info['device_id'], delay, device_obj is not None
                            )
                            
                    except Exception as e:
                        self.logger.error(f"Failed to create device {device_info['device_id']}: {e}")
                        if reporting_manager and hasattr(reporting_manager, 'record_registration_attempt'):
                            reporting_manager.record_registration_attempt(
                                device_info['device_id'], delay, False
                            )
                
                self.devices = successful_devices
                self.stats['devices_created'] = len(self.devices)
                self.logger.info(f"Created {len(self.devices)} devices successfully with throttling")
                
                if reporting_manager:
                    reporting_manager.stats['devices_registered'] = len(self.devices) 
            
            if not self.devices:
                self.logger.warning("No devices were created successfully in throttled setup.")
                return False

            # Validate all created devices - Create a NEW session for validation
            self.logger.info("Validating devices with initial telemetry (throttled setup)...")
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context, limit=10), timeout=timeout) as validation_session:
                
                successful_validations = 0
                
                # Validate devices sequentially with small delays to prevent adapter overload
                for i, device in enumerate(self.devices):
                    try:
                        # Add small delay between validations to prevent 503 errors
                        if i > 0:
                            await asyncio.sleep(0.2)  # 200ms delay between validations
                        
                        result = await self.validate_device_http(validation_session, device)
                        if result:
                            successful_validations += 1
                            self.stats['validation_success'] += 1 # Update internal stats
                        else:
                            self.stats['validation_failed'] += 1 # Update internal stats
                    except Exception as e:
                        self.logger.error(f"Validation exception for device {device.device_id}: {e}")
                        self.stats['validation_failed'] += 1 # Update internal stats

            self.logger.info(f"Validation complete (throttled setup): {successful_validations}/{len(self.devices)} devices validated")

            # Pass validation stats to ReportingManager if it's provided
            if reporting_manager and hasattr(reporting_manager, 'update_validation_stats'):
                reporting_manager.update_validation_stats(
                    success_count=self.stats['validation_success'],
                    failure_count=self.stats['validation_failed'],
                    total_devices=len(self.devices)
                )
            elif reporting_manager: # Fallback if specific method doesn't exist, update directly
                reporting_manager.performance_metrics['validation_success'] = self.stats['validation_success']
                reporting_manager.performance_metrics['validation_failed'] = self.stats['validation_failed']


            if successful_validations == len(self.devices):
                self.logger.info("✅ All devices validated successfully (throttled setup)! Ready to start load testing.")
            else:
                self.logger.warning(f"⚠️  Only {successful_validations}/{len(self.devices)} devices validated (throttled setup). Some may fail during load testing.")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Infrastructure setup with throttling failed: {e}", exc_info=True)
            return False

    async def _create_device_with_throttling(self, session: aiohttp.ClientSession, tenant_id: str, device_index: int, 
                                           delay: float, reporting_manager: Optional['ReportingManager'] = None) -> Optional[Device]:
        """Create a single device with throttling delay using the provided session."""
        # Apply throttling delay
        if delay > 0:
            self.logger.debug(f"Applying registration delay of {delay:.2f}s for device index {device_index}")
            await asyncio.sleep(delay)
        
        # Ensure device_id is unique, e.g., by using the global device_index
        device_id = f"device-{device_index:04d}" # Padded for more devices
        
        device_obj = None
        success = False
        try:
            # Call the existing create_device which now should handle session internally or be passed one
            # Assuming create_device can take a session or creates its own if not passed
            device_obj = await self.create_device(session, tenant_id, device_id_suffix=f"{device_index:04d}")
            
            if device_obj:
                # Attempt to set credentials
                # The create_device method should ideally return a full Device object with password
                # If not, set_device_credentials would be needed here.
                # For now, assuming create_device handles password generation and setting.
                # If set_device_credentials is still separate:
                # cred_success = await self.set_device_credentials(session, device_obj)
                # success = cred_success
                success = True # Assuming create_device now returns a fully formed device
            
            # Record registration metrics
            if reporting_manager and hasattr(reporting_manager, 'record_registration_attempt'):
                reporting_manager.record_registration_attempt(
                    device_id, delay, success
                )
            
            return device_obj if success else None
            
        except Exception as e:
            self.logger.error(f"Exception in _create_device_with_throttling for {device_id}: {e}", exc_info=True)
            # Record failed registration
            if reporting_manager and hasattr(reporting_manager, 'record_registration_attempt'):
                reporting_manager.record_registration_attempt(
                    device_id, delay, False # Explicitly False on exception
                )
            # Do not re-raise if you want to continue with other devices, 
            # but return None to indicate failure for this one.
            return None

    async def validate_device_registration(self, device: Device, tenant_id: str) -> bool:
        """Validate device registration and credentials."""
        # Use HTTPS or HTTP based on TLS setting
        protocol_scheme = "https" if self.config.use_tls else "http"
        url = f"{protocol_scheme}://{self.config.http_adapter_ip}:{self.config.http_adapter_port}/telemetry"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        auth = aiohttp.BasicAuth(f"{device.auth_id}@{tenant_id}", device.password)
        payload = {
            "validation": True, 
            "timestamp": int(time.time()),
            "device_id": device.device_id,
            "temperature": 25.0,
            "humidity": 60.0,
            "message": "validation_test"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, auth=auth) as response:
                    if 200 <= response.status < 300:
                        is_valid = True
                        self.logger.info(f"Device {device.device_id} validated successfully.")
                    else:
                        is_valid = False
                        error_text = await response.text()
                        self.logger.warning(f"Validation failed for device {device.device_id}: {response.status} - {error_text}")
        
        except Exception as e:
            is_valid = False
            self.logger.error(f"Exception validating device {device.device_id}: {e}")
        
        # Update reporting manager stats
        if is_valid:
            self.reporting_manager.stats['validation_success'] += 1
        else:
            self.reporting_manager.stats['validation_failed'] += 1
        
        return is_valid
