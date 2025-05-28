"""
Configuration module for Hono Load Test Suite.
Contains configuration dataclasses and environment loading utilities.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import logging
import aiohttp


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
    http_insecure_port: int = 8080
    mqtt_adapter_port: int = 8883
    mqtt_insecure_port: int = 1883
    coap_adapter_port: int = 5684
    amqp_adapter_port: int = 5671
    lora_adapter_port: int = 8085
    
    # Registry authentication
    registry_username: str = "hono-client@HONO"
    registry_password: str = "secret"
    
    # Add registry_auth property for convenience
    @property
    def registry_auth(self) -> 'aiohttp.BasicAuth':
        import aiohttp
        return aiohttp.BasicAuth(self.registry_username, self.registry_password)
    
    use_tls: bool = True
    use_mqtt_tls: bool = True  # Separate control for MQTT TLS
    verify_ssl: bool = False
    ca_file_path: Optional[str] = None
    
    # Client options
    curl_options: str = "--insecure"
    mosquitto_options: str = "--insecure"
    http_timeout: int = 30
    mqtt_keepalive: int = 60
    mqtt_connect_timeout: int = 10  # MQTT connection timeout in seconds
    
    # Add explicit tenant/device options
    my_tenant: Optional[str] = None
    my_device: Optional[str] = None 
    my_password: Optional[str] = None
    
    def __post_init__(self):
        """Post-initialization to set default paths."""
        if self.ca_file_path is None:
            # Try to find truststore.pem in common locations
            possible_paths = [
                "../truststore.pem",  # From python-script-organize directory
                "truststore.pem",     # Current directory
                "/tmp/truststore.pem"  # Linux location
            ]
            for path in possible_paths:
                if Path(path).exists():
                    self.ca_file_path = path
                    break


async def load_config_from_env(config: HonoConfig, env_file: str = "hono.env") -> None:
    """Load configuration from environment file and update the config object."""
    logger = logging.getLogger(__name__)
    
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
    config.registry_ip = os.getenv('REGISTRY_IP', config.registry_ip)
    config.registry_port = int(os.getenv('REGISTRY_PORT', str(config.registry_port)))
    config.registry_username = os.getenv('REGISTRY_USERNAME', config.registry_username)
    config.registry_password = os.getenv('REGISTRY_PASSWORD', config.registry_password)
    
    config.http_adapter_ip = os.getenv('HTTP_ADAPTER_IP', config.http_adapter_ip)
    config.http_adapter_port = int(os.getenv('HTTP_ADAPTER_PORT', str(config.http_adapter_port)))
    
    config.mqtt_adapter_ip = os.getenv('MQTT_ADAPTER_IP', config.mqtt_adapter_ip)
    config.mqtt_adapter_port = int(os.getenv('MQTT_ADAPTER_PORT', str(config.mqtt_adapter_port)))
    config.mqtt_insecure_port = int(os.getenv('MQTT_INSECURE_PORT', str(config.mqtt_insecure_port)))
    
    config.coap_adapter_ip = os.getenv('COAP_ADAPTER_IP', config.coap_adapter_ip)
    config.coap_adapter_port = int(os.getenv('COAP_ADAPTER_PORT', config.coap_adapter_port))
    
    config.amqp_adapter_ip = os.getenv('AMQP_ADAPTER_IP', config.amqp_adapter_ip)
    config.amqp_adapter_port = int(os.getenv('AMQP_ADAPTER_PORT', config.amqp_adapter_port))
    
    config.lora_adapter_ip = os.getenv('LORA_ADAPTER_IP', config.lora_adapter_ip)
    config.lora_adapter_port = int(os.getenv('LORA_ADAPTER_PORT', config.lora_adapter_port))
    
    # TLS/SSL Configuration
    config.use_tls = os.getenv('USE_TLS', 'true').lower() == 'true'
    config.use_mqtt_tls = os.getenv('USE_MQTT_TLS', os.getenv('USE_TLS', 'true')).lower() == 'true'
    config.verify_ssl = os.getenv('VERIFY_SSL', 'false').lower() == 'true'
    config.ca_file_path = os.getenv('CA_FILE_PATH', config.ca_file_path) 
    
    # Re-run post_init if ca_file_path was not set by env, to allow default search
    if not os.getenv('CA_FILE_PATH') and config.ca_file_path is None:
        config.__post_init__() # Allow default search if not set by env
    
    # Client options
    config.curl_options = os.getenv('CURL_OPTIONS', config.curl_options)
    config.mosquitto_options = os.getenv('MOSQUITTO_OPTIONS', config.mosquitto_options)
    config.http_timeout = int(os.getenv('HTTP_TIMEOUT', config.http_timeout))
    config.mqtt_keepalive = int(os.getenv('MQTT_KEEPALIVE', config.mqtt_keepalive))
    config.mqtt_connect_timeout = int(os.getenv('MQTT_CONNECT_TIMEOUT', config.mqtt_connect_timeout))
    
    # Existing tenant/device configuration
    config.my_tenant = os.getenv('MY_TENANT')
    config.my_device = os.getenv('MY_DEVICE')
    config.my_password = os.getenv('MY_PWD')
    
    logger.info(f"Loaded configuration: Registry={config.registry_ip}:{config.registry_port}")
    logger.info(f"MQTT: {config.mqtt_adapter_ip}:{config.mqtt_adapter_port} (TLS: {config.use_mqtt_tls})")
    logger.info(f"HTTP: {config.http_adapter_ip}:{config.http_adapter_port}")
    if config.ca_file_path:
        logger.info(f"CA File Path: {config.ca_file_path} (Exists: {Path(config.ca_file_path).exists() if config.ca_file_path else 'N/A'})")
    else:
        logger.warning("CA File Path is not set.")
