"""
Shared utilities for Hono Load Test Suite
"""

import json
import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

@dataclass
class HonoConfig:
    """Configuration for Hono endpoints."""
    registry_ip: str
    registry_port: int
    http_adapter_ip: str
    http_adapter_port: int
    mqtt_adapter_ip: str
    mqtt_adapter_port: int
    coap_adapter_ip: str
    coap_adapter_port: int
    amqp_adapter_ip: str
    amqp_adapter_port: int
    lora_adapter_ip: str
    lora_adapter_port: int
    use_tls: bool = True
    verify_ssl: bool = False
    ca_file: Optional[str] = None

@dataclass
class TestStats:
    """Test execution statistics."""
    start_time: float
    end_time: Optional[float] = None
    messages_sent: int = 0
    messages_failed: int = 0
    devices_registered: int = 0
    tenants_registered: int = 0
    validation_success: int = 0
    validation_failed: int = 0

def load_config_from_env() -> HonoConfig:
    """Load Hono configuration from environment variables."""
    import os
    
    return HonoConfig(
        registry_ip=os.getenv('REGISTRY_IP', 'localhost'),
        registry_port=int(os.getenv('REGISTRY_PORT', '28443')),
        http_adapter_ip=os.getenv('HTTP_ADAPTER_IP', 'localhost'),
        http_adapter_port=int(os.getenv('HTTP_ADAPTER_PORT', '8443')),
        mqtt_adapter_ip=os.getenv('MQTT_ADAPTER_IP', 'localhost'),
        mqtt_adapter_port=int(os.getenv('MQTT_ADAPTER_PORT', '8883')),
        coap_adapter_ip=os.getenv('COAP_ADAPTER_IP', 'localhost'),
        coap_adapter_port=int(os.getenv('COAP_ADAPTER_PORT', '5684')),
        amqp_adapter_ip=os.getenv('AMQP_ADAPTER_IP', 'localhost'),
        amqp_adapter_port=int(os.getenv('AMQP_ADAPTER_PORT', '5671')),
        lora_adapter_ip=os.getenv('LORA_ADAPTER_IP', 'localhost'),
        lora_adapter_port=int(os.getenv('LORA_ADAPTER_PORT', '8080')),
        use_tls=os.getenv('USE_TLS', 'true').lower() == 'true',
        verify_ssl=os.getenv('VERIFY_SSL', 'false').lower() == 'true',
        ca_file=os.getenv('CA_FILE_PATH')
    )

def setup_logging(service_name: str, level: str = 'INFO') -> logging.Logger:
    """Setup logging for a service."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=f'%(asctime)s - {service_name.upper()} - %(levelname)s - %(message)s'
    )
    return logging.getLogger(service_name)

def generate_realistic_sensor_data() -> Dict:
    """Generate realistic IoT sensor data."""
    import random
    
    return {
        "temperature": round(random.uniform(18.0, 35.0), 2),
        "humidity": round(random.uniform(30.0, 90.0), 2),
        "pressure": round(random.uniform(980.0, 1030.0), 2),
        "battery": round(random.uniform(20.0, 100.0), 2),
        "signal_strength": random.randint(-100, -30),
        "location": {
            "lat": round(random.uniform(-90.0, 90.0), 6),
            "lon": round(random.uniform(-180.0, 180.0), 6)
        },
        "motion_detected": random.choice([True, False]),
        "light_level": random.randint(0, 1000)
    }

async def wait_for_file(file_path: str, max_wait_time: int = 300) -> bool:
    """Wait for a file to be created."""
    import asyncio
    import os
    
    start_time = time.time()
    while time.time() - start_time < max_wait_time:
        if os.path.exists(file_path):
            return True
        await asyncio.sleep(1)
    return False

def calculate_success_rate(sent: int, failed: int) -> float:
    """Calculate success rate percentage."""
    total = sent + failed
    return (sent / total * 100) if total > 0 else 0.0
