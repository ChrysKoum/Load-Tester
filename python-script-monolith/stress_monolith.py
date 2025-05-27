#!/usr/bin/env python3
"""
Hono Load Test Suite - Python Script
A comprehensive load testing tool for Eclipse Hono with multi-protocol support.
"""

import os
import sys
import json
import time
import uuid
import random
import argparse
import logging
import asyncio
import aiohttp
import threading
import ssl
import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional, Tuple
import paho.mqtt.client as mqtt
from dataclasses import dataclass
from pathlib import Path

# Try to import reporting libraries
try:
    import matplotlib.pyplot as plt
    import pandas as pd
    REPORTING_AVAILABLE = True
except ImportError:
    REPORTING_AVAILABLE = False

# Try to import additional protocol libraries
try:
    import coap
    COAP_AVAILABLE = True
except ImportError:
    COAP_AVAILABLE = False

try:
    import amqp
    AMQP_AVAILABLE = True
except ImportError:
    AMQP_AVAILABLE = False

@dataclass
class HonoConfig:
    """Configuration for Hono endpoints and credentials."""
    registry_ip: str = "localhost"
    http_adapter_ip: str = "localhost"
    mqtt_adapter_ip: str = "localhost"
    coap_adapter_ip: str = "localhost"
    amqp_adapter_ip: str = "localhost"
    lora_adapter_ip: str = "localhost"
    
    registry_port: int = 28443
    http_adapter_port: int = 8443
    mqtt_adapter_port: int = 8883
    mqtt_insecure_port: int = 1883  # Add the insecure MQTT port
    coap_adapter_port: int = 5684
    amqp_adapter_port: int = 5671
    lora_adapter_port: int = 8080
    
    use_tls: bool = True
    use_mqtt_tls: bool = True  # Separate control for MQTT TLS
    verify_ssl: bool = False
    ca_file_path: Optional[str] = None
    
    # Client options
    curl_options: str = "--insecure"
    mosquitto_options: str = "--insecure"
    http_timeout: int = 30
    mqtt_keepalive: int = 60
    
    # Add explicit tenant/device options
    my_tenant: Optional[str] = None
    my_device: Optional[str] = None 
    my_password: Optional[str] = None

@dataclass
class Device:
    """Represents a device in the load test."""
    device_id: str
    tenant_id: str
    password: str
    auth_id: str = None
    
    def __post_init__(self):
        if self.auth_id is None:
            self.auth_id = self.device_id

class HonoLoadTester:
    """Main class for Hono load testing."""
    
    def __init__(self, config: HonoConfig):
        self.config = config
        self.tenants: List[str] = []
        self.devices: List[Device] = []
        self.running = False
        self.stats = {
            'messages_sent': 0,
            'messages_failed': 0,
            'devices_registered': 0,
            'tenants_registered': 0,
            'validation_success': 0,
            'validation_failed': 0
        }
        
        # Detailed metrics for reporting
        self.time_series_data = {
            'timestamps': [],
            'messages_sent': [],
            'messages_failed': [],
            'msg_rate': []
        }
        
        self.protocol_stats = {}  # Track stats per protocol
        self.test_start_time = None
        self.test_end_time = None
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    async def load_config_from_env(self, env_file: str = "hono.env"):
        """Load configuration from environment file."""
        env_path = Path(env_file)
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('export '):
                        line = line[7:]  # Remove 'export '
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        # Remove quotes if present
                        value = value.strip('"\'')
                        os.environ[key] = value
    
        # Update config from environment variables
        self.config.registry_ip = os.getenv('REGISTRY_IP', self.config.registry_ip)
        self.config.registry_port = int(os.getenv('REGISTRY_PORT', self.config.registry_port))
        
        self.config.http_adapter_ip = os.getenv('HTTP_ADAPTER_IP', self.config.http_adapter_ip)
        self.config.http_adapter_port = int(os.getenv('HTTP_ADAPTER_PORT', self.config.http_adapter_port))
        
        self.config.mqtt_adapter_ip = os.getenv('MQTT_ADAPTER_IP', self.config.mqtt_adapter_ip)
        self.config.mqtt_adapter_port = int(os.getenv('MQTT_ADAPTER_PORT', self.config.mqtt_adapter_port))
        self.config.mqtt_insecure_port = int(os.getenv('MQTT_INSECURE_PORT', self.config.mqtt_insecure_port))
        
        self.config.coap_adapter_ip = os.getenv('COAP_ADAPTER_IP', self.config.coap_adapter_ip)
        self.config.coap_adapter_port = int(os.getenv('COAP_ADAPTER_PORT', self.config.coap_adapter_port))
        
        self.config.amqp_adapter_ip = os.getenv('AMQP_ADAPTER_IP', self.config.amqp_adapter_ip)
        self.config.amqp_adapter_port = int(os.getenv('AMQP_ADAPTER_PORT', self.config.amqp_adapter_port))
        
        self.config.lora_adapter_ip = os.getenv('LORA_ADAPTER_IP', self.config.lora_adapter_ip)
        self.config.lora_adapter_port = int(os.getenv('LORA_ADAPTER_PORT', self.config.lora_adapter_port))
        
        # TLS/SSL Configuration
        self.config.use_tls = os.getenv('USE_TLS', 'true').lower() == 'true'
        self.config.use_mqtt_tls = os.getenv('USE_MQTT_TLS', os.getenv('USE_TLS', 'true')).lower() == 'true'
        self.config.verify_ssl = os.getenv('VERIFY_SSL', 'false').lower() == 'true'
        self.config.ca_file_path = os.getenv('CA_FILE_PATH')
        
        # Client options
        self.config.curl_options = os.getenv('CURL_OPTIONS', self.config.curl_options)
        self.config.mosquitto_options = os.getenv('MOSQUITTO_OPTIONS', self.config.mosquitto_options)
        self.config.http_timeout = int(os.getenv('HTTP_TIMEOUT', self.config.http_timeout))
        self.config.mqtt_keepalive = int(os.getenv('MQTT_KEEPALIVE', self.config.mqtt_keepalive))
        
        # Existing tenant/device configuration
        self.config.my_tenant = os.getenv('MY_TENANT')
        self.config.my_device = os.getenv('MY_DEVICE')
        self.config.my_password = os.getenv('MY_PWD')
        
        self.logger.info(f"Loaded configuration: Registry={self.config.registry_ip}:{self.config.registry_port}")
        self.logger.info(f"MQTT: {self.config.mqtt_adapter_ip}:{self.config.mqtt_adapter_port} (TLS: {self.config.use_mqtt_tls})")
        self.logger.info(f"HTTP: {self.config.http_adapter_ip}:{self.config.http_adapter_port}")
        
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
    
    async def setup_infrastructure(self, num_tenants: int = 5, num_devices: int = 10):
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
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Create tenants
            tenant_tasks = [self.create_tenant(session) for _ in range(num_tenants)]
            tenant_results = await asyncio.gather(*tenant_tasks, return_exceptions=True)
            
            self.tenants = [t for t in tenant_results if isinstance(t, str)]
            
            if len(self.tenants) == 0:
                self.logger.error("No tenants created successfully!")
                return False
            
            self.logger.info(f"Created {len(self.tenants)} tenants successfully")
            
            # Distribute devices evenly across tenants
            devices_per_tenant = num_devices // len(self.tenants)
            remaining_devices = num_devices % len(self.tenants)
            
            device_tasks = []
            for i, tenant_id in enumerate(self.tenants):
                tenant_device_count = devices_per_tenant + (1 if i < remaining_devices else 0)
                for _ in range(tenant_device_count):
                    device_tasks.append(self.create_device(session, tenant_id))
            
            device_results = await asyncio.gather(*device_tasks, return_exceptions=True)
            self.devices = [d for d in device_results if isinstance(d, Device)]
            
            if len(self.devices) == 0:
                self.logger.error("No devices created successfully!")
                return False
            
            self.logger.info(f"Created {len(self.devices)} devices successfully")
            
            # Validate all devices
            self.logger.info("Validating devices with initial telemetry...")
            validation_tasks = [self.validate_device_http(session, device) for device in self.devices]
            validation_results = await asyncio.gather(*validation_tasks, return_exceptions=True)
            
            successful_validations = sum(1 for r in validation_results if r is True)
            self.logger.info(f"Validation complete: {successful_validations}/{len(self.devices)} devices validated")
            
            if successful_validations == len(self.devices):
                self.logger.info("✅ All devices validated successfully! Ready to start load testing.")
                return True
            else:
                self.logger.warning(f"⚠️  Only {successful_validations}/{len(self.devices)} devices validated. Some may fail during load testing.")
                return True
    
    def mqtt_telemetry_worker(self, device: Device, message_interval: float, protocol: str = "telemetry"):
        """Worker function for MQTT telemetry publishing."""
        # Increment device count for this protocol
        self.protocol_stats['mqtt']['devices'] += 1
        
        client = mqtt.Client()
        client.username_pw_set(f"{device.auth_id}@{device.tenant_id}", device.password)
        
        # Determine port and TLS settings
        if self.config.use_mqtt_tls:
            mqtt_port = self.config.mqtt_adapter_port  # Usually 8883
            if self.config.ca_file_path and os.path.exists(self.config.ca_file_path):
                client.tls_set(ca_certs=self.config.ca_file_path)
            else:
                client.tls_set()
            
            if not self.config.verify_ssl:
                client.tls_insecure_set(True)
                
            self.logger.debug(f"Using MQTT TLS on port {mqtt_port}")
        else:
            mqtt_port = self.config.mqtt_insecure_port  # Usually 1883
            self.logger.debug(f"Using MQTT insecure on port {mqtt_port}")
        
        connected = False
        
        def on_connect(client, userdata, flags, rc):
            nonlocal connected
            if rc == 0:
                connected = True
                self.logger.debug(f"MQTT connected for device {device.device_id}")
            else:
                self.logger.error(f"MQTT connection failed for device {device.device_id}: {rc}")
        
        client.on_connect = on_connect
        
        try:
            self.logger.debug(f"Connecting to {self.config.mqtt_adapter_ip}:{mqtt_port}")
            client.connect(self.config.mqtt_adapter_ip, mqtt_port, self.config.mqtt_keepalive)
            client.loop_start()
            
            # Wait for connection
            start_time = time.time()
            while not connected and (time.time() - start_time) < 10:
                time.sleep(0.1)
            
            if not connected:
                self.logger.error(f"MQTT connection timeout for device {device.device_id}")
                return
            
            message_count = 0
            while self.running and connected:
                payload = {
                    "device_id": device.device_id,
                    "tenant_id": device.tenant_id,
                    "timestamp": int(time.time()),
                    "message_count": message_count,
                    "protocol": "mqtt",
                    "temperature": round(random.uniform(18.0, 35.0), 2),
                    "humidity": round(random.uniform(30.0, 90.0), 2),
                    "pressure": round(random.uniform(980.0, 1030.0), 2),
                    "battery": round(random.uniform(20.0, 100.0), 2),
                    "signal_strength": random.randint(-100, -30)
                }
                
                topic = protocol  # "telemetry" or "event"
                qos = 0 if protocol == "telemetry" else 1
                
                result = client.publish(topic, json.dumps(payload), qos=qos)
                
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    self.stats['messages_sent'] += 1
                    self.protocol_stats['mqtt']['messages_sent'] += 1
                    message_count += 1
                else:
                    self.stats['messages_failed'] += 1
                    self.protocol_stats['mqtt']['messages_failed'] += 1
                    self.logger.warning(f"MQTT publish failed for device {device.device_id}: {result.rc}")
                
                time.sleep(message_interval)
                
        except Exception as e:
            self.logger.error(f"MQTT worker error for device {device.device_id}: {e}")
            self.stats['messages_failed'] += 1
        finally:
            try:
                client.disconnect()
                client.loop_stop()
            except:
                pass
    def generate_report(self, report_dir: str = "./reports"):
        """Generate detailed test report with charts."""
        self.test_end_time = datetime.datetime.now()
        test_duration = (self.test_end_time - self.test_start_time).total_seconds()
        
        # Create reports directory if it doesn't exist
        reports_path = Path(report_dir)
        reports_path.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamp for report filenames
        timestamp = self.test_end_time.strftime("%Y%m%d_%H%M%S")
        report_file = reports_path / f"hono_test_report_{timestamp}.txt"
        charts_file = reports_path / f"hono_test_charts_{timestamp}.png"
        
        # Calculate overall stats
        total_sent = self.stats['messages_sent']
        total_failed = self.stats['messages_failed']
        success_rate = (total_sent / max(1, total_sent + total_failed)) * 100
        avg_rate = total_sent / test_duration if test_duration > 0 else 0
        
        # Write text report
        with open(report_file, 'w') as f:
            f.write("=" * 60 + "\n")
            f.write("HONO LOAD TEST DETAILED REPORT\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"Test Date: {self.test_start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Test Duration: {test_duration:.2f} seconds\n\n")
            
            f.write("CONFIGURATION\n")
            f.write("-" * 40 + "\n")
            f.write(f"Registry: {self.config.registry_ip}:{self.config.registry_port}\n")
            f.write(f"MQTT Adapter: {self.config.mqtt_adapter_ip}:{self.config.mqtt_adapter_port}\n")
            f.write(f"HTTP Adapter: {self.config.http_adapter_ip}:{self.config.http_adapter_port}\n")
            f.write(f"MQTT TLS: {self.config.use_mqtt_tls}\n")
            f.write(f"HTTP TLS: {self.config.use_tls}\n\n")
            
            f.write("TEST INFRASTRUCTURE\n")
            f.write("-" * 40 + "\n")
            f.write(f"Tenants: {len(self.tenants)}\n")
            f.write(f"Devices: {len(self.devices)}\n")
            f.write(f"Devices per Tenant: {len(self.devices) / max(1, len(self.tenants)):.1f}\n\n")
            
            f.write("VALIDATION RESULTS\n")
            f.write("-" * 40 + "\n")
            f.write(f"Validation Success: {self.stats['validation_success']}\n")
            f.write(f"Validation Failed: {self.stats['validation_failed']}\n")
            f.write(f"Validation Rate: {self.stats['validation_success'] / max(1, len(self.devices)) * 100:.1f}%\n\n")
            
            f.write("LOAD TEST RESULTS\n")
            f.write("-" * 40 + "\n")
            f.write(f"Messages Sent: {total_sent}\n")
            f.write(f"Messages Failed: {total_failed}\n")
            f.write(f"Success Rate: {success_rate:.1f}%\n")
            f.write(f"Average Message Rate: {avg_rate:.2f} messages/second\n\n")
            
            f.write("PROTOCOL BREAKDOWN\n")
            f.write("-" * 40 + "\n")
            for proto, stats in self.protocol_stats.items():
                proto_success_rate = 100
                if stats['messages_sent'] + stats['messages_failed'] > 0:
                    proto_success_rate = (stats['messages_sent'] / (stats['messages_sent'] + stats['messages_failed'])) * 100
                
                f.write(f"Protocol: {proto.upper()}\n")
                f.write(f"  Devices: {stats['devices']}\n")
                f.write(f"  Messages Sent: {stats['messages_sent']}\n")
                f.write(f"  Messages Failed: {stats['messages_failed']}\n")
                f.write(f"  Success Rate: {proto_success_rate:.1f}%\n\n")
            
            f.write("=" * 60 + "\n")
            f.write(f"Report generated at: {self.test_end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        self.logger.info(f"Text report saved to: {report_file}")
        
        # Generate charts if matplotlib is available
        if REPORTING_AVAILABLE and len(self.time_series_data['timestamps']) > 0:
            try:
                # Create a figure with multiple subplots
                fig, axs = plt.subplots(2, 1, figsize=(10, 8))
                fig.suptitle('Hono Load Test Results', fontsize=16)
                
                # Message count over time
                axs[0].plot(self.time_series_data['timestamps'], 
                        self.time_series_data['messages_sent'], 
                        'b-', label='Messages Sent')
                axs[0].plot(self.time_series_data['timestamps'], 
                        self.time_series_data['messages_failed'], 
                        'r-', label='Messages Failed')
                axs[0].set_ylabel('Message Count')
                axs[0].set_title('Message Counts Over Time')
                axs[0].legend()
                axs[0].grid(True)
                
                # Message rate over time
                axs[1].plot(self.time_series_data['timestamps'], 
                        self.time_series_data['msg_rate'], 
                        'g-', label='Message Rate')
                axs[1].set_xlabel('Time')
                axs[1].set_ylabel('Messages per Second')
                axs[1].set_title('Message Rate Over Time')
                axs[1].grid(True)
                
                # Adjust layout and save
                plt.tight_layout(rect=[0, 0, 1, 0.95])
                plt.savefig(charts_file)
                plt.close()
                
                self.logger.info(f"Charts saved to: {charts_file}")
                
            except Exception as e:
                self.logger.error(f"Failed to generate charts: {e}")
        elif not REPORTING_AVAILABLE:
            self.logger.warning("Charts not generated: matplotlib or pandas not available. Install with 'pip install matplotlib pandas'")
    
    def print_final_stats(self):
        """Print final statistics."""
        print("\n" + "="*50)
        print("FINAL LOAD TEST STATISTICS")
        print("="*50)
        print(f"Tenants registered: {self.stats['tenants_registered']}")
        print(f"Devices registered: {self.stats['devices_registered']}")
        print(f"Devices validated: {self.stats['validation_success']}")
        print(f"Validation failures: {self.stats['validation_failed']}")
        print(f"Messages sent: {self.stats['messages_sent']}")
        print(f"Messages failed: {self.stats['messages_failed']}")
        print(f"Success rate: {(self.stats['messages_sent'] / max(1, self.stats['messages_sent'] + self.stats['messages_failed']) * 100):.1f}%")
        
        # Protocol breakdown
        if self.protocol_stats:
            print("\nPROTOCOL BREAKDOWN:")
            for proto, stats in self.protocol_stats.items():
                proto_success_rate = 100
                if stats['messages_sent'] + stats['messages_failed'] > 0:
                    proto_success_rate = (stats['messages_sent'] / (stats['messages_sent'] + stats['messages_failed'])) * 100
                
                print(f"  {proto.upper()}: {stats['messages_sent']} sent, {stats['messages_failed']} failed, "
                    f"{proto_success_rate:.1f}% success rate")
        
        print("="*50)

    async def http_telemetry_worker(self, device: Device, message_interval: float, protocol: str = "telemetry"):
        """Worker function for HTTP telemetry publishing."""
        # Increment device count for this protocol
        self.protocol_stats['http']['devices'] += 1
        
        # Configure SSL context
        ssl_context = None
        if self.config.use_tls:
            if self.config.ca_file_path and os.path.exists(self.config.ca_file_path):
                ssl_context = ssl.create_default_context(cafile=self.config.ca_file_path)
            else:
                ssl_context = ssl.create_default_context()
            
            if not self.config.verify_ssl:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        timeout = aiohttp.ClientTimeout(total=self.config.http_timeout)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Use HTTPS or HTTP based on TLS setting
            protocol_scheme = "https" if self.config.use_tls else "http"
            url = f"{protocol_scheme}://{self.config.http_adapter_ip}:{self.config.http_adapter_port}/{protocol}"
            
            headers = {"Content-Type": "application/json"}
            auth = aiohttp.BasicAuth(f"{device.auth_id}@{device.tenant_id}", device.password)
            
            message_count = 0
            while self.running:
                payload = {
                    "device_id": device.device_id,
                    "tenant_id": device.tenant_id,
                    "timestamp": int(time.time()),
                    "message_count": message_count,
                    "protocol": "http",
                    "temperature": round(random.uniform(18.0, 35.0), 2),
                    "humidity": round(random.uniform(30.0, 90.0), 2),
                    "pressure": round(random.uniform(980.0, 1030.0), 2),
                    "battery": round(random.uniform(20.0, 100.0), 2),
                    "signal_strength": random.randint(-100, -30)
                }
                
                try:
                    async with session.post(url, json=payload, headers=headers, auth=auth) as response:
                        if 200 <= response.status < 300:
                            self.stats['messages_sent'] += 1
                            self.protocol_stats['http']['messages_sent'] += 1
                            message_count += 1
                        else:
                            self.stats['messages_failed'] += 1
                            self.protocol_stats['http']['messages_failed'] += 1
                            self.logger.warning(f"HTTP publish failed for device {device.device_id}: {response.status}")
                except Exception as e:
                    self.stats['messages_failed'] += 1
                    self.logger.error(f"HTTP worker error for device {device.device_id}: {e}")
                
                await asyncio.sleep(message_interval)
    
    def start_load_test(self, protocols: List[str], message_interval: float, message_type: str = "telemetry"):
        """Start the load testing with specified protocols."""
        if not self.devices:
            self.logger.error("No devices available for load testing!")
            return
        
        self.logger.info(f"Starting load test with {len(self.devices)} devices using protocols: {protocols}")
        self.logger.info(f"Message interval: {message_interval}s, Type: {message_type}")
        
        # Initialize test start time and protocol stats
        self.test_start_time = datetime.datetime.now()
        for protocol in protocols:
            self.protocol_stats[protocol.lower()] = {
                'messages_sent': 0,
                'messages_failed': 0,
                'devices': 0
            }
        
        self.running = True
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
                        target=self.mqtt_telemetry_worker,
                        args=(device, message_interval, message_type)
                    )
                elif protocol.lower() == "http":
                    worker = threading.Thread(
                        target=lambda d=device: asyncio.run(
                            self.http_telemetry_worker(d, message_interval, message_type)
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
                        target=self.mqtt_telemetry_worker,
                        args=(device, message_interval, message_type)
                    )
                else:
                    worker = threading.Thread(
                        target=lambda d=device: asyncio.run(
                            self.http_telemetry_worker(d, message_interval, message_type)
                        )
                    )
                workers.append(worker)
                worker.start()
        
        try:
            # Monitor stats
            self.monitor_stats()
            
            # Wait for user to stop
            input("\nPress Enter to stop the load test...\n")
            
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        finally:
            self.logger.info("Stopping load test...")
            self.running = False
            
            # Wait for all workers to finish
            for worker in workers:
                worker.join(timeout=5)
            
            self.print_final_stats()
    
    def monitor_stats(self):
        """Monitor and print statistics during load testing."""
        def stats_monitor():
            last_sent = 0
            last_time = time.time()
            
            while self.running:
                time.sleep(10)  # Print stats every 10 seconds
                current_time = time.time()
                current_sent = self.stats['messages_sent']
                elapsed = current_time - last_time
                
                # Calculate message rate
                rate = (current_sent - last_sent) / elapsed if elapsed > 0 else 0
                
                # Store time series data for reporting
                self.time_series_data['timestamps'].append(datetime.datetime.now())
                self.time_series_data['messages_sent'].append(current_sent)
                self.time_series_data['messages_failed'].append(self.stats['messages_failed'])
                self.time_series_data['msg_rate'].append(rate)
                
                # Log current stats
                self.logger.info(
                    f"Stats - Sent: {current_sent}, Failed: {self.stats['messages_failed']}, "
                    f"Rate: {rate:.1f} msg/s"
                )
                
                # Update for next interval
                last_sent = current_sent
                last_time = current_time
    
        stats_thread = threading.Thread(target=stats_monitor)
        stats_thread.daemon = True
        stats_thread.start()
    
    def print_final_stats(self):
        """Print final statistics."""
        print("\n" + "="*50)
        print("FINAL LOAD TEST STATISTICS")
        print("="*50)
        print(f"Tenants registered: {self.stats['tenants_registered']}")
        print(f"Devices registered: {self.stats['devices_registered']}")
        print(f"Devices validated: {self.stats['validation_success']}")
        print(f"Validation failures: {self.stats['validation_failed']}")
        print(f"Messages sent: {self.stats['messages_sent']}")
        print(f"Messages failed: {self.stats['messages_failed']}")
        print(f"Success rate: {(self.stats['messages_sent'] / max(1, self.stats['messages_sent'] + self.stats['messages_failed']) * 100):.1f}%")
        print("="*50)

def main():
    parser = argparse.ArgumentParser(description="Hono Load Test Suite")
    parser.add_argument("--mode", choices=["10fast", "100slow", "custom"], default="10fast",
                   help="Test mode: 10fast (10 devices, 5.75s interval), 100slow (100 devices, 60s interval), or custom")
    parser.add_argument("--protocols", nargs="+", choices=["mqtt", "http", "coap", "amqp", "lora"], 
                    default=["mqtt"], help="Protocols to use for testing")
    parser.add_argument("--kind", choices=["telemetry", "event"], default="telemetry",
                    help="Type of messages to send")
    parser.add_argument("--tenants", type=int, default=5, help="Number of tenants to create")
    parser.add_argument("--devices", type=int, help="Number of devices to create (overrides mode)")
    parser.add_argument("--interval", type=float, help="Message interval in seconds (overrides mode)")
    parser.add_argument("--env-file", default="hono.env", help="Environment file to load")
    parser.add_argument("--setup-only", action="store_true", help="Only setup infrastructure, don't run load test")
    parser.add_argument("--mqtt-insecure", action="store_true", help="Use insecure MQTT port (1883) instead of TLS")
    parser.add_argument("--no-ssl-verify", action="store_true", help="Disable SSL certificate verification")
    parser.add_argument("--tiny", action="store_true", help="Run a tiny test with 2 tenants and 2 devices")
    parser.add_argument("--report", action="store_true", help="Generate detailed test report with charts")
    parser.add_argument("--report-dir", default="./reports", help="Directory to save test reports")

    args = parser.parse_args()

    # Configure based on mode
    if args.tiny:
        num_devices = 2
        message_interval = 10.0
        args.tenants = 2
        print("Running in tiny test mode (2 tenants, 2 devices)")
    elif args.mode == "10fast":
        num_devices = args.devices or 10
        message_interval = args.interval or 5.75
    elif args.mode == "100slow":
        num_devices = args.devices or 100
        message_interval = args.interval or 60.0
    else:  # custom
        num_devices = args.devices or 10
        message_interval = args.interval or 10.0
    
    # Initialize tester
    config = HonoConfig()
    
    # Override TLS settings if requested
    if args.mqtt_insecure:
        config.use_mqtt_tls = False
    if args.no_ssl_verify:
        config.verify_ssl = False
    
    tester = HonoLoadTester(config)
    
    async def run_test():
        # Load configuration
        await tester.load_config_from_env(args.env_file)
        
        # Setup infrastructure
        success = await tester.setup_infrastructure(args.tenants, num_devices)
        if not success:
            print("❌ Infrastructure setup failed!")
            return 1
        
        if args.setup_only:
            print("✅ Infrastructure setup complete. Use --setup-only=false to run load test.")
            return 0
        
        # Start load test
        print(f"\n🚀 Starting load test: {num_devices} devices, {message_interval}s interval")
        print(f"Protocols: {args.protocols}, Message type: {args.kind}")
        print("Press Enter when ready to start...")
        input()
        
        tester.start_load_test(args.protocols, message_interval, args.kind)
        
        # Generate report if requested
        if args.report:
            tester.generate_report(args.report_dir)
            print(f"\n📊 Test report generated in: {args.report_dir}")
        
        return 0
    
    try:
        exit_code = asyncio.run(run_test())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
