#!/usr/bin/env python3
"""
Hono Load Test - Validator Service
Validates device connectivity and authentication before load testing.
"""

import os
import sys
import json
import time
import asyncio
import aiohttp
import aiofiles
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class ValidationResult:
    device_id: str
    tenant_id: str
    success: bool
    response_code: Optional[int]
    error_message: Optional[str]
    response_time: float

class HonoValidator:
    """Service for validating device connectivity and authentication."""
    
    def __init__(self):
        self.devices = []
        self.validation_results: List[ValidationResult] = []
        
        # Setup logging
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - VALIDATOR - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.http_adapter_ip = os.getenv('HTTP_ADAPTER_IP', 'localhost')
        self.http_adapter_port = int(os.getenv('HTTP_ADAPTER_PORT', '8443'))
        self.mqtt_adapter_ip = os.getenv('MQTT_ADAPTER_IP', 'localhost')
        self.mqtt_adapter_port = int(os.getenv('MQTT_ADAPTER_PORT', '8883'))
        self.verify_ssl = os.getenv('VERIFY_SSL', 'false').lower() == 'true'
        self.timeout = int(os.getenv('HTTP_TIMEOUT', '30'))
        
        self.logger.info("Validator initialized")
    
    async def wait_for_registrar(self, max_wait_time: int = 300):
        """Wait for registrar to complete and load device data."""
        self.logger.info("Waiting for registrar to complete...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            try:
                # Check if registrar has completed
                async with aiofiles.open('/app/shared/status.json', 'r') as f:
                    status_content = await f.read()
                    status = json.loads(status_content)
                    
                    if status.get('service') == 'registrar' and status.get('status') == 'completed':
                        self.logger.info("Registrar completed. Loading device data...")
                        return await self.load_device_data()
                
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            
            await asyncio.sleep(5)
        
        self.logger.error(f"Registrar did not complete within {max_wait_time} seconds")
        return False
    
    async def load_device_data(self):
        """Load device data from shared storage."""
        try:
            async with aiofiles.open('/app/shared/devices.json', 'r') as f:
                devices_content = await f.read()
                devices_data = json.loads(devices_content)
                self.devices = devices_data
                
            self.logger.info(f"Loaded {len(self.devices)} devices for validation")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load device data: {e}")
            return False
    
    async def validate_device_http(self, session: aiohttp.ClientSession, device: dict) -> ValidationResult:
        """Validate a single device using HTTP telemetry."""
        device_id = device['id']
        tenant_id = device['tenant_id']
        auth_id = device['auth_id']
        password = device['password']
        
        url = f"https://{self.http_adapter_ip}:{self.http_adapter_port}/telemetry"
        headers = {"Content-Type": "application/json"}
        auth = aiohttp.BasicAuth(f"{auth_id}@{tenant_id}", password)
        
        payload = {
            "validation": True,
            "timestamp": int(time.time()),
            "device_id": device_id,
            "temperature": 25.0,
            "humidity": 60.0,
            "message": "validation_test"
        }
        
        start_time = time.time()
        
        try:
            async with session.post(url, json=payload, headers=headers, auth=auth, ssl=self.verify_ssl) as response:
                response_time = time.time() - start_time
                
                if 200 <= response.status < 300:
                    self.logger.debug(f"Device {device_id} validation successful ({response.status})")
                    return ValidationResult(
                        device_id=device_id,
                        tenant_id=tenant_id,
                        success=True,
                        response_code=response.status,
                        error_message=None,
                        response_time=response_time
                    )
                else:
                    error_text = await response.text()
                    self.logger.warning(f"Device {device_id} validation failed: {response.status} - {error_text}")
                    return ValidationResult(
                        device_id=device_id,
                        tenant_id=tenant_id,
                        success=False,
                        response_code=response.status,
                        error_message=f"HTTP {response.status}: {error_text}",
                        response_time=response_time
                    )
                    
        except Exception as e:
            response_time = time.time() - start_time
            self.logger.error(f"Device {device_id} validation exception: {e}")
            return ValidationResult(
                device_id=device_id,
                tenant_id=tenant_id,
                success=False,
                response_code=None,
                error_message=str(e),
                response_time=response_time
            )
    
    async def validate_all_devices(self):
        """Validate all devices concurrently."""
        if not self.devices:
            self.logger.error("No devices to validate")
            return False
        
        self.logger.info(f"Starting validation of {len(self.devices)} devices...")
        
        connector = aiohttp.TCPConnector(ssl=self.verify_ssl, limit=50)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Validate devices concurrently
            validation_tasks = [
                self.validate_device_http(session, device) 
                for device in self.devices
            ]
            
            self.validation_results = await asyncio.gather(*validation_tasks, return_exceptions=True)
            
            # Filter out exceptions and convert to ValidationResult objects
            valid_results = []
            for result in self.validation_results:
                if isinstance(result, ValidationResult):
                    valid_results.append(result)
                else:
                    self.logger.error(f"Validation task failed with exception: {result}")
            
            self.validation_results = valid_results
        
        # Calculate statistics
        successful_validations = sum(1 for r in self.validation_results if r.success)
        total_devices = len(self.devices)
        success_rate = (successful_validations / total_devices * 100) if total_devices > 0 else 0
        
        avg_response_time = sum(r.response_time for r in self.validation_results) / len(self.validation_results) if self.validation_results else 0
        
        self.logger.info(f"Validation complete: {successful_validations}/{total_devices} devices ({success_rate:.1f}%)")
        self.logger.info(f"Average response time: {avg_response_time:.3f}s")
        
        # Log failed validations
        for result in self.validation_results:
            if not result.success:
                self.logger.warning(f"Failed: {result.device_id} - {result.error_message}")
        
        # Save validation results
        await self.save_validation_results()
        
        return successful_validations > 0
    
    async def save_validation_results(self):
        """Save validation results to shared storage."""
        try:
            # Prepare validation summary
            successful_validations = sum(1 for r in self.validation_results if r.success)
            total_devices = len(self.validation_results)
            
            validation_summary = {
                'service': 'validator',
                'status': 'completed',
                'timestamp': time.time(),
                'total_devices': total_devices,
                'successful_validations': successful_validations,
                'success_rate': (successful_validations / total_devices * 100) if total_devices > 0 else 0,
                'avg_response_time': sum(r.response_time for r in self.validation_results) / len(self.validation_results) if self.validation_results else 0,
                'results': [
                    {
                        'device_id': r.device_id,
                        'tenant_id': r.tenant_id,
                        'success': r.success,
                        'response_code': r.response_code,
                        'error_message': r.error_message,
                        'response_time': r.response_time
                    }
                    for r in self.validation_results
                ]
            }
            
            async with aiofiles.open('/app/shared/validation_results.json', 'w') as f:
                await f.write(json.dumps(validation_summary, indent=2))
            
            # Update status
            status = {
                'service': 'validator',
                'status': 'completed',
                'timestamp': time.time(),
                'validation_success_rate': validation_summary['success_rate'],
                'devices_validated': successful_validations,
                'total_devices': total_devices
            }
            
            async with aiofiles.open('/app/shared/status.json', 'w') as f:
                await f.write(json.dumps(status, indent=2))
            
            self.logger.info("Validation results saved to shared volume")
            
        except Exception as e:
            self.logger.error(f"Failed to save validation results: {e}")
    
    def print_validation_summary(self):
        """Print a summary of validation results."""
        if not self.validation_results:
            return
        
        successful = sum(1 for r in self.validation_results if r.success)
        total = len(self.validation_results)
        
        print("\n" + "="*60)
        print("DEVICE VALIDATION SUMMARY")
        print("="*60)
        print(f"Total devices: {total}")
        print(f"Successful validations: {successful}")
        print(f"Failed validations: {total - successful}")
        print(f"Success rate: {(successful/total*100):.1f}%")
        
        if successful == total:
            print("✅ ALL DEVICES VALIDATED SUCCESSFULLY!")
            print("Ready to proceed with load testing.")
        elif successful > 0:
            print("⚠️  PARTIAL VALIDATION SUCCESS")
            print("Some devices may fail during load testing.")
        else:
            print("❌ VALIDATION FAILED")
            print("No devices were validated successfully.")
        
        print("="*60)

async def main():
    """Main entry point for the validator service."""
    validator = HonoValidator()
    
    try:
        # Wait for registrar to complete and load device data
        if not await validator.wait_for_registrar():
            sys.exit(1)
        
        # Validate all devices
        success = await validator.validate_all_devices()
        
        # Print summary
        validator.print_validation_summary()
        
        if not success:
            sys.exit(1)
        
    except KeyboardInterrupt:
        validator.logger.info("Validator service interrupted")
        sys.exit(1)
    except Exception as e:
        validator.logger.error(f"Validator service failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
