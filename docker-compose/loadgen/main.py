#!/usr/bin/env python3
"""
Hono Load Test - Load Generator Service
Generates load using multiple protocols (MQTT, HTTP, CoAP, AMQP, LoRa).
"""

import os
import sys
import json
import time
import uuid
import random
import asyncio
import aiohttp
import aiofiles
import logging
import threading
import socket
import struct
from typing import List, Dict, Optional
import paho.mqtt.client as mqtt
from dataclasses import dataclass

# Additional imports for new protocols
try:
    import aiocoap
    from aiocoap.protocol import Context
    from aiocoap.message import Message
    COAP_AVAILABLE = True
except ImportError:
    COAP_AVAILABLE = False

try:
    import pika
    AMQP_AVAILABLE = True
except ImportError:
    AMQP_AVAILABLE = False

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

@dataclass
class LoadGenStats:
    messages_sent: int = 0
    messages_failed: int = 0
    total_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    last_message_time: float = 0.0

class ProtocolHandler:
    """Base class for protocol-specific handlers."""
    
    def __init__(self, name: str, logger: logging.Logger):
        self.name = name
        self.logger = logger
        self.stats = LoadGenStats()
        self.running = False
    
    async def start(self, devices: List[dict], message_interval: float, message_type: str):
        """Start the protocol handler."""
        raise NotImplementedError
    
    def stop(self):
        """Stop the protocol handler."""
        self.running = False

class MQTTHandler(ProtocolHandler):
    """MQTT protocol handler."""
    
    def __init__(self, logger: logging.Logger):
        super().__init__("MQTT", logger)
        self.mqtt_adapter_ip = os.getenv('MQTT_ADAPTER_IP', 'localhost')
        self.mqtt_adapter_port = int(os.getenv('MQTT_ADAPTER_PORT', '8883'))
        self.use_tls = os.getenv('USE_TLS', 'true').lower() == 'true'
        self.verify_ssl = os.getenv('VERIFY_SSL', 'false').lower() == 'true'
        self.keepalive = int(os.getenv('MQTT_KEEPALIVE', '60'))
        self.workers = []
    
    def mqtt_worker(self, device: dict, message_interval: float, message_type: str):
        """Worker function for a single MQTT device."""
        device_id = device['id']
        tenant_id = device['tenant_id']
        auth_id = device['auth_id']
        password = device['password']
        
        client = mqtt.Client()
        client.username_pw_set(f"{auth_id}@{tenant_id}", password)
        
        if self.use_tls:
            client.tls_set()
            if not self.verify_ssl:
                client.tls_insecure_set(True)
        
        connected = False
        
        def on_connect(client, userdata, flags, rc):
            nonlocal connected
            if rc == 0:
                connected = True
                self.logger.debug(f"MQTT device {device_id} connected")
            else:
                self.logger.error(f"MQTT device {device_id} connection failed: {rc}")
        
        def on_publish(client, userdata, mid):
            # Message published successfully
            pass
        
        client.on_connect = on_connect
        client.on_publish = on_publish
        
        try:
            client.connect(self.mqtt_adapter_ip, self.mqtt_adapter_port, self.keepalive)
            client.loop_start()
            
            # Wait for connection
            wait_time = 0
            while not connected and wait_time < 30:
                time.sleep(0.1)
                wait_time += 0.1
            
            if not connected:
                self.logger.error(f"MQTT device {device_id} failed to connect within timeout")
                return
            
            message_count = 0
            while self.running:
                payload = {
                    "device_id": device_id,
                    "tenant_id": tenant_id,
                    "timestamp": int(time.time()),
                    "message_count": message_count,
                    "protocol": "mqtt",
                    "temperature": random.uniform(18.0, 35.0),
                    "humidity": random.uniform(30.0, 90.0),
                    "pressure": random.uniform(980.0, 1030.0),
                    "battery": random.uniform(20.0, 100.0),
                    "signal_strength": random.randint(-100, -30)
                }
                
                topic = message_type  # "telemetry" or "event"
                qos = 0 if message_type == "telemetry" else 1
                
                start_time = time.time()
                result = client.publish(topic, json.dumps(payload), qos=qos)
                
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    response_time = time.time() - start_time
                    self.stats.messages_sent += 1
                    self.stats.total_response_time += response_time
                    self.stats.min_response_time = min(self.stats.min_response_time, response_time)
                    self.stats.max_response_time = max(self.stats.max_response_time, response_time)
                    self.stats.last_message_time = time.time()
                    message_count += 1
                else:
                    self.stats.messages_failed += 1
                    self.logger.warning(f"MQTT publish failed for device {device_id}: {result.rc}")
                
                time.sleep(message_interval)
                
        except Exception as e:
            self.logger.error(f"MQTT worker error for device {device_id}: {e}")
            self.stats.messages_failed += 1
        finally:
            try:
                client.disconnect()
                client.loop_stop()
            except:
                pass
    
    async def start(self, devices: List[dict], message_interval: float, message_type: str):
        """Start MQTT load generation."""
        self.logger.info(f"Starting MQTT handler with {len(devices)} devices")
        self.running = True
        
        # Start worker threads for each device
        for device in devices:
            worker = threading.Thread(
                target=self.mqtt_worker,
                args=(device, message_interval, message_type)
            )
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
    
    def stop(self):
        """Stop MQTT handler."""
        super().stop()
        # Workers will stop naturally when self.running becomes False

class HTTPHandler(ProtocolHandler):
    """HTTP protocol handler."""
    
    def __init__(self, logger: logging.Logger):
        super().__init__("HTTP", logger)
        self.http_adapter_ip = os.getenv('HTTP_ADAPTER_IP', 'localhost')
        self.http_adapter_port = int(os.getenv('HTTP_ADAPTER_PORT', '8443'))
        self.verify_ssl = os.getenv('VERIFY_SSL', 'false').lower() == 'true'
        self.timeout = int(os.getenv('HTTP_TIMEOUT', '30'))
        self.tasks = []
    
    async def http_worker(self, device: dict, message_interval: float, message_type: str):
        """Worker coroutine for a single HTTP device."""
        device_id = device['id']
        tenant_id = device['tenant_id']
        auth_id = device['auth_id']
        password = device['password']
        
        connector = aiohttp.TCPConnector(ssl=self.verify_ssl, limit=10)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            url = f"https://{self.http_adapter_ip}:{self.http_adapter_port}/{message_type}"
            headers = {"Content-Type": "application/json"}
            auth = aiohttp.BasicAuth(f"{auth_id}@{tenant_id}", password)
            
            message_count = 0
            while self.running:
                payload = {
                    "device_id": device_id,
                    "tenant_id": tenant_id,
                    "timestamp": int(time.time()),
                    "message_count": message_count,
                    "protocol": "http",
                    "temperature": random.uniform(18.0, 35.0),
                    "humidity": random.uniform(30.0, 90.0),
                    "pressure": random.uniform(980.0, 1030.0),
                    "battery": random.uniform(20.0, 100.0),
                    "location": {
                        "lat": random.uniform(-90.0, 90.0),
                        "lon": random.uniform(-180.0, 180.0)
                    }
                }
                
                try:
                    start_time = time.time()
                    async with session.post(url, json=payload, headers=headers, auth=auth, ssl=self.verify_ssl) as response:
                        response_time = time.time() - start_time
                        
                        if 200 <= response.status < 300:
                            self.stats.messages_sent += 1
                            self.stats.total_response_time += response_time
                            self.stats.min_response_time = min(self.stats.min_response_time, response_time)
                            self.stats.max_response_time = max(self.stats.max_response_time, response_time)
                            self.stats.last_message_time = time.time()
                            message_count += 1
                        else:
                            self.stats.messages_failed += 1
                            self.logger.warning(f"HTTP publish failed for device {device_id}: {response.status}")
                except Exception as e:
                    self.stats.messages_failed += 1
                    self.logger.error(f"HTTP worker error for device {device_id}: {e}")
                
                await asyncio.sleep(message_interval)
    
    async def start(self, devices: List[dict], message_interval: float, message_type: str):
        """Start HTTP load generation."""
        self.logger.info(f"Starting HTTP handler with {len(devices)} devices")
        self.running = True
        
        # Start worker coroutines for each device
        for device in devices:
            task = asyncio.create_task(
                self.http_worker(device, message_interval, message_type)
            )
            self.tasks.append(task)
      def stop(self):
        """Stop HTTP handler."""
        super().stop()
        # Tasks will stop naturally when self.running becomes False

class CoAPHandler(ProtocolHandler):
    """CoAP protocol handler."""
    
    def __init__(self, logger: logging.Logger):
        super().__init__("CoAP", logger)
        self.coap_adapter_ip = os.getenv('COAP_ADAPTER_IP', 'localhost')
        self.coap_adapter_port = int(os.getenv('COAP_ADAPTER_PORT', '5684'))
        self.use_tls = os.getenv('USE_TLS', 'true').lower() == 'true'
        self.timeout = int(os.getenv('COAP_TIMEOUT', '30'))
        self.tasks = []
        
        if not COAP_AVAILABLE:
            self.logger.warning("aiocoap library not available, CoAP handler disabled")
    
    async def coap_worker(self, device: dict, message_interval: float, message_type: str):
        """Worker coroutine for a single CoAP device."""
        if not COAP_AVAILABLE:
            self.logger.error("aiocoap library not available")
            return
            
        device_id = device['id']
        tenant_id = device['tenant_id']
        auth_id = device['auth_id']
        password = device['password']
        
        try:
            # Create CoAP context
            context = await Context.create_client_context()
            
            # Create URI
            scheme = "coaps" if self.use_tls else "coap"
            uri = f"{scheme}://{self.coap_adapter_ip}:{self.coap_adapter_port}/{message_type}"
            
            message_count = 0
            while self.running:
                payload = {
                    "device_id": device_id,
                    "tenant_id": tenant_id,
                    "timestamp": int(time.time()),
                    "message_count": message_count,
                    "protocol": "coap",
                    "temperature": random.uniform(18.0, 35.0),
                    "humidity": random.uniform(30.0, 90.0),
                    "pressure": random.uniform(980.0, 1030.0),
                    "voltage": random.uniform(3.0, 5.0),
                    "signal_strength": random.randint(-100, -30)
                }
                
                try:
                    start_time = time.time()
                    
                    # Create CoAP message
                    request = Message(
                        code=aiocoap.POST,
                        uri=uri,
                        payload=json.dumps(payload).encode('utf-8')
                    )
                    
                    # Add authentication headers if available
                    # Note: CoAP authentication handling depends on Hono's implementation
                    if auth_id and password:
                        # This is a simplified auth approach, actual implementation may vary
                        auth_header = f"{auth_id}@{tenant_id}:{password}"
                        request.opt.authorization = auth_header.encode('utf-8')
                    
                    # Send request
                    response = await asyncio.wait_for(
                        context.request(request).response,
                        timeout=self.timeout
                    )
                    
                    response_time = time.time() - start_time
                    
                    if response.code.is_successful():
                        self.stats.messages_sent += 1
                        self.stats.total_response_time += response_time
                        self.stats.min_response_time = min(self.stats.min_response_time, response_time)
                        self.stats.max_response_time = max(self.stats.max_response_time, response_time)
                        self.stats.last_message_time = time.time()
                        message_count += 1
                    else:
                        self.stats.messages_failed += 1
                        self.logger.warning(f"CoAP publish failed for device {device_id}: {response.code}")
                        
                except asyncio.TimeoutError:
                    self.stats.messages_failed += 1
                    self.logger.warning(f"CoAP timeout for device {device_id}")
                except Exception as e:
                    self.stats.messages_failed += 1
                    self.logger.error(f"CoAP worker error for device {device_id}: {e}")
                
                await asyncio.sleep(message_interval)
                
        except Exception as e:
            self.logger.error(f"CoAP worker setup error for device {device_id}: {e}")
            self.stats.messages_failed += 1
        finally:
            try:
                await context.shutdown()
            except:
                pass
    
    async def start(self, devices: List[dict], message_interval: float, message_type: str):
        """Start CoAP load generation."""
        if not COAP_AVAILABLE:
            self.logger.error("aiocoap library not available, cannot start CoAP handler")
            return
            
        self.logger.info(f"Starting CoAP handler with {len(devices)} devices")
        self.running = True
        
        # Start worker coroutines for each device
        for device in devices:
            task = asyncio.create_task(
                self.coap_worker(device, message_interval, message_type)
            )
            self.tasks.append(task)
    
    def stop(self):
        """Stop CoAP handler."""
        super().stop()
        # Tasks will stop naturally when self.running becomes False

class AMQPHandler(ProtocolHandler):
    """AMQP protocol handler."""
    
    def __init__(self, logger: logging.Logger):
        super().__init__("AMQP", logger)
        self.amqp_adapter_ip = os.getenv('AMQP_ADAPTER_IP', 'localhost')
        self.amqp_adapter_port = int(os.getenv('AMQP_ADAPTER_PORT', '5671'))
        self.use_tls = os.getenv('USE_TLS', 'true').lower() == 'true'
        self.timeout = int(os.getenv('AMQP_TIMEOUT', '30'))
        self.workers = []
        
        if not AMQP_AVAILABLE:
            self.logger.warning("pika library not available, AMQP handler disabled")
    
    def amqp_worker(self, device: dict, message_interval: float, message_type: str):
        """Worker function for a single AMQP device."""
        if not AMQP_AVAILABLE:
            self.logger.error("pika library not available")
            return
            
        device_id = device['id']
        tenant_id = device['tenant_id']
        auth_id = device['auth_id']
        password = device['password']
        
        try:
            # Create connection parameters
            credentials = pika.PlainCredentials(f"{auth_id}@{tenant_id}", password)
            
            if self.use_tls:
                # Use SSL context for TLS
                import ssl
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                parameters = pika.ConnectionParameters(
                    host=self.amqp_adapter_ip,
                    port=self.amqp_adapter_port,
                    credentials=credentials,
                    ssl_options=pika.SSLOptions(ssl_context)
                )
            else:
                parameters = pika.ConnectionParameters(
                    host=self.amqp_adapter_ip,
                    port=self.amqp_adapter_port,
                    credentials=credentials
                )
            
            connection = None
            channel = None
            
            message_count = 0
            while self.running:
                try:
                    # Reconnect if needed
                    if not connection or connection.is_closed:
                        connection = pika.BlockingConnection(parameters)
                        channel = connection.channel()
                    
                    payload = {
                        "device_id": device_id,
                        "tenant_id": tenant_id,
                        "timestamp": int(time.time()),
                        "message_count": message_count,
                        "protocol": "amqp",
                        "temperature": random.uniform(18.0, 35.0),
                        "humidity": random.uniform(30.0, 90.0),
                        "pressure": random.uniform(980.0, 1030.0),
                        "power": random.uniform(0.1, 10.0),
                        "current": random.uniform(0.1, 2.0)
                    }
                    
                    # Set routing key based on message type
                    routing_key = f"{message_type}"  # "telemetry" or "event"
                    
                    start_time = time.time()
                    
                    # Publish message
                    channel.basic_publish(
                        exchange='',
                        routing_key=routing_key,
                        body=json.dumps(payload),
                        properties=pika.BasicProperties(
                            delivery_mode=2,  # Make message persistent
                            content_type='application/json'
                        )
                    )
                    
                    response_time = time.time() - start_time
                    
                    self.stats.messages_sent += 1
                    self.stats.total_response_time += response_time
                    self.stats.min_response_time = min(self.stats.min_response_time, response_time)
                    self.stats.max_response_time = max(self.stats.max_response_time, response_time)
                    self.stats.last_message_time = time.time()
                    message_count += 1
                    
                except Exception as e:
                    self.stats.messages_failed += 1
                    self.logger.error(f"AMQP publish error for device {device_id}: {e}")
                    
                    # Close connection on error to force reconnect
                    try:
                        if connection and not connection.is_closed:
                            connection.close()
                    except:
                        pass
                    connection = None
                
                time.sleep(message_interval)
                
        except Exception as e:
            self.logger.error(f"AMQP worker setup error for device {device_id}: {e}")
            self.stats.messages_failed += 1
        finally:
            try:
                if connection and not connection.is_closed:
                    connection.close()
            except:
                pass
    
    async def start(self, devices: List[dict], message_interval: float, message_type: str):
        """Start AMQP load generation."""
        if not AMQP_AVAILABLE:
            self.logger.error("pika library not available, cannot start AMQP handler")
            return
            
        self.logger.info(f"Starting AMQP handler with {len(devices)} devices")
        self.running = True
        
        # Start worker threads for each device (AMQP uses blocking I/O)
        for device in devices:
            worker = threading.Thread(
                target=self.amqp_worker,
                args=(device, message_interval, message_type)
            )
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
    
    def stop(self):
        """Stop AMQP handler."""
        super().stop()
        # Workers will stop naturally when self.running becomes False

class LoRaHandler(ProtocolHandler):
    """LoRa protocol handler (simulated via WebSocket or HTTP)."""
    
    def __init__(self, logger: logging.Logger):
        super().__init__("LoRa", logger)
        self.lora_adapter_ip = os.getenv('LORA_ADAPTER_IP', 'localhost')
        self.lora_adapter_port = int(os.getenv('LORA_ADAPTER_PORT', '8080'))
        self.use_tls = os.getenv('USE_TLS', 'true').lower() == 'true'
        self.timeout = int(os.getenv('LORA_TIMEOUT', '30'))
        self.connection_type = os.getenv('LORA_CONNECTION_TYPE', 'websocket')  # 'websocket' or 'http'
        self.tasks = []
        
        if self.connection_type == 'websocket' and not WEBSOCKETS_AVAILABLE:
            self.logger.warning("websockets library not available, falling back to HTTP for LoRa")
            self.connection_type = 'http'
    
    async def lora_websocket_worker(self, device: dict, message_interval: float, message_type: str):
        """LoRa worker using WebSocket connection."""
        device_id = device['id']
        tenant_id = device['tenant_id']
        auth_id = device['auth_id']
        password = device['password']
        
        scheme = "wss" if self.use_tls else "ws"
        uri = f"{scheme}://{self.lora_adapter_ip}:{self.lora_adapter_port}/lora/{message_type}"
        
        try:
            # WebSocket headers for authentication
            headers = {
                "Authorization": f"Basic {auth_id}@{tenant_id}:{password}"
            }
            
            async with websockets.connect(uri, extra_headers=headers) as websocket:
                self.logger.debug(f"LoRa WebSocket connected for device {device_id}")
                
                message_count = 0
                while self.running:
                    payload = {
                        "device_id": device_id,
                        "tenant_id": tenant_id,
                        "timestamp": int(time.time()),
                        "message_count": message_count,
                        "protocol": "lora",
                        "temperature": random.uniform(-10.0, 50.0),
                        "humidity": random.uniform(20.0, 95.0),
                        "battery": random.uniform(10.0, 100.0),
                        "rssi": random.randint(-120, -60),
                        "snr": random.uniform(-10.0, 10.0),
                        "frequency": random.choice([868.1, 868.3, 868.5, 867.1, 867.3, 867.5, 867.7, 867.9])
                    }
                    
                    try:
                        start_time = time.time()
                        await websocket.send(json.dumps(payload))
                        
                        # Wait for acknowledgment (optional)
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=5)
                            response_time = time.time() - start_time
                            
                            self.stats.messages_sent += 1
                            self.stats.total_response_time += response_time
                            self.stats.min_response_time = min(self.stats.min_response_time, response_time)
                            self.stats.max_response_time = max(self.stats.max_response_time, response_time)
                            self.stats.last_message_time = time.time()
                            message_count += 1
                            
                        except asyncio.TimeoutError:
                            # No acknowledgment received, but message was sent
                            response_time = time.time() - start_time
                            self.stats.messages_sent += 1
                            self.stats.total_response_time += response_time
                            self.stats.min_response_time = min(self.stats.min_response_time, response_time)
                            self.stats.max_response_time = max(self.stats.max_response_time, response_time)
                            self.stats.last_message_time = time.time()
                            message_count += 1
                            
                    except Exception as e:
                        self.stats.messages_failed += 1
                        self.logger.error(f"LoRa WebSocket send error for device {device_id}: {e}")
                    
                    await asyncio.sleep(message_interval)
                    
        except Exception as e:
            self.logger.error(f"LoRa WebSocket worker error for device {device_id}: {e}")
            self.stats.messages_failed += 1
    
    async def lora_http_worker(self, device: dict, message_interval: float, message_type: str):
        """LoRa worker using HTTP connection."""
        device_id = device['id']
        tenant_id = device['tenant_id']
        auth_id = device['auth_id']
        password = device['password']
        
        connector = aiohttp.TCPConnector(ssl=(not self.use_tls or False), limit=10)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            scheme = "https" if self.use_tls else "http"
            url = f"{scheme}://{self.lora_adapter_ip}:{self.lora_adapter_port}/lora/{message_type}"
            headers = {"Content-Type": "application/json"}
            auth = aiohttp.BasicAuth(f"{auth_id}@{tenant_id}", password)
            
            message_count = 0
            while self.running:
                payload = {
                    "device_id": device_id,
                    "tenant_id": tenant_id,
                    "timestamp": int(time.time()),
                    "message_count": message_count,
                    "protocol": "lora",
                    "temperature": random.uniform(-10.0, 50.0),
                    "humidity": random.uniform(20.0, 95.0),
                    "battery": random.uniform(10.0, 100.0),
                    "rssi": random.randint(-120, -60),
                    "snr": random.uniform(-10.0, 10.0),
                    "spreading_factor": random.choice([7, 8, 9, 10, 11, 12]),
                    "data_rate": random.choice(["SF7BW125", "SF8BW125", "SF9BW125", "SF10BW125"])
                }
                
                try:
                    start_time = time.time()
                    async with session.post(url, json=payload, headers=headers, auth=auth) as response:
                        response_time = time.time() - start_time
                        
                        if 200 <= response.status < 300:
                            self.stats.messages_sent += 1
                            self.stats.total_response_time += response_time
                            self.stats.min_response_time = min(self.stats.min_response_time, response_time)
                            self.stats.max_response_time = max(self.stats.max_response_time, response_time)
                            self.stats.last_message_time = time.time()
                            message_count += 1
                        else:
                            self.stats.messages_failed += 1
                            self.logger.warning(f"LoRa HTTP publish failed for device {device_id}: {response.status}")
                except Exception as e:
                    self.stats.messages_failed += 1
                    self.logger.error(f"LoRa HTTP worker error for device {device_id}: {e}")
                
                await asyncio.sleep(message_interval)
    
    async def start(self, devices: List[dict], message_interval: float, message_type: str):
        """Start LoRa load generation."""
        self.logger.info(f"Starting LoRa handler with {len(devices)} devices using {self.connection_type}")
        self.running = True
        
        # Start worker coroutines for each device
        for device in devices:
            if self.connection_type == 'websocket' and WEBSOCKETS_AVAILABLE:
                task = asyncio.create_task(
                    self.lora_websocket_worker(device, message_interval, message_type)
                )
            else:
                task = asyncio.create_task(
                    self.lora_http_worker(device, message_interval, message_type)
                )
            self.tasks.append(task)
    
    def stop(self):
        """Stop LoRa handler."""
        super().stop()
        # Tasks will stop naturally when self.running becomes False

class HonoLoadGenerator:
    """Main load generator service."""
    
    def __init__(self):
        self.devices = []
        self.handlers: Dict[str, ProtocolHandler] = {}
        self.running = False
        
        # Setup logging
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - LOADGEN - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.protocols = os.getenv('PROTOCOLS', 'mqtt').split(',')
        self.message_type = os.getenv('MESSAGE_TYPE', 'telemetry')
        self.message_interval = float(os.getenv('MESSAGE_INTERVAL', '10'))
          # Initialize protocol handlers
        self.handlers['mqtt'] = MQTTHandler(self.logger)
        self.handlers['http'] = HTTPHandler(self.logger)
        self.handlers['coap'] = CoAPHandler(self.logger)
        self.handlers['amqp'] = AMQPHandler(self.logger)
        self.handlers['lora'] = LoRaHandler(self.logger)
        
        self.logger.info(f"LoadGen initialized - Protocols: {self.protocols}, Interval: {self.message_interval}s")
    
    async def wait_for_validator(self, max_wait_time: int = 300):
        """Wait for validator to complete and load device data."""
        self.logger.info("Waiting for validator to complete...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            try:
                # Check if validator has completed
                async with aiofiles.open('/app/shared/status.json', 'r') as f:
                    status_content = await f.read()
                    status = json.loads(status_content)
                    
                    if status.get('service') == 'validator' and status.get('status') == 'completed':
                        self.logger.info("Validator completed. Loading device data...")
                        return await self.load_device_data()
                
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            
            await asyncio.sleep(5)
        
        self.logger.error(f"Validator did not complete within {max_wait_time} seconds")
        return False
    
    async def load_device_data(self):
        """Load device data from shared storage."""
        try:
            async with aiofiles.open('/app/shared/devices.json', 'r') as f:
                devices_content = await f.read()
                self.devices = json.loads(devices_content)
                
            self.logger.info(f"Loaded {len(self.devices)} devices for load generation")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load device data: {e}")
            return False
    
    async def start_load_generation(self):
        """Start load generation with configured protocols."""
        if not self.devices:
            self.logger.error("No devices available for load generation")
            return False
        
        self.logger.info(f"Starting load generation with {len(self.devices)} devices")
        self.logger.info(f"Protocols: {self.protocols}, Message type: {self.message_type}, Interval: {self.message_interval}s")
        
        self.running = True
        
        # Distribute devices across protocols
        devices_per_protocol = len(self.devices) // len(self.protocols)
        device_index = 0
        
        start_tasks = []
        
        for protocol in self.protocols:
            protocol = protocol.strip().lower()
            
            if protocol not in self.handlers:
                self.logger.warning(f"Protocol {protocol} not implemented, skipping")
                continue
            
            # Calculate devices for this protocol
            if device_index + devices_per_protocol <= len(self.devices):
                protocol_devices = self.devices[device_index:device_index + devices_per_protocol]
                device_index += devices_per_protocol
            else:
                protocol_devices = self.devices[device_index:]
                device_index = len(self.devices)
            
            if protocol_devices:
                self.logger.info(f"Starting {protocol.upper()} with {len(protocol_devices)} devices")
                start_tasks.append(
                    self.handlers[protocol].start(protocol_devices, self.message_interval, self.message_type)
                )
        
        # Handle any remaining devices with the first protocol
        if device_index < len(self.devices):
            remaining_devices = self.devices[device_index:]
            first_protocol = self.protocols[0].strip().lower()
            if first_protocol in self.handlers:
                self.logger.info(f"Assigning {len(remaining_devices)} remaining devices to {first_protocol.upper()}")
                start_tasks.append(
                    self.handlers[first_protocol].start(remaining_devices, self.message_interval, self.message_type)
                )
        
        # Start all protocol handlers
        if start_tasks:
            await asyncio.gather(*start_tasks)
        
        # Start monitoring
        await self.monitor_load_generation()
        
        return True
    
    async def monitor_load_generation(self):
        """Monitor load generation and print statistics."""
        self.logger.info("Load generation started. Monitoring statistics...")
        
        last_stats = {}
        
        try:
            while self.running:
                await asyncio.sleep(10)  # Print stats every 10 seconds
                
                # Collect stats from all handlers
                total_sent = 0
                total_failed = 0
                total_response_time = 0.0
                min_response_time = float('inf')
                max_response_time = 0.0
                active_protocols = []
                
                for protocol, handler in self.handlers.items():
                    if handler.stats.messages_sent > 0 or handler.stats.messages_failed > 0:
                        total_sent += handler.stats.messages_sent
                        total_failed += handler.stats.messages_failed
                        total_response_time += handler.stats.total_response_time
                        
                        if handler.stats.min_response_time != float('inf'):
                            min_response_time = min(min_response_time, handler.stats.min_response_time)
                        max_response_time = max(max_response_time, handler.stats.max_response_time)
                        
                        active_protocols.append(protocol.upper())
                
                # Calculate rates
                current_sent = total_sent
                last_sent = last_stats.get('sent', 0)
                send_rate = (current_sent - last_sent) / 10
                
                # Calculate average response time
                avg_response_time = (total_response_time / total_sent) if total_sent > 0 else 0
                
                if min_response_time == float('inf'):
                    min_response_time = 0
                
                # Log statistics
                self.logger.info(
                    f"Stats - Sent: {total_sent}, Failed: {total_failed}, "
                    f"Rate: {send_rate:.1f} msg/s, Avg RT: {avg_response_time:.3f}s, "
                    f"Protocols: {', '.join(active_protocols)}"
                )
                
                last_stats = {'sent': current_sent}
                
                # Save stats periodically
                await self.save_load_stats(total_sent, total_failed, send_rate, avg_response_time)
                
        except asyncio.CancelledError:
            self.logger.info("Monitoring cancelled")
        except Exception as e:
            self.logger.error(f"Monitoring error: {e}")
    
    async def save_load_stats(self, total_sent: int, total_failed: int, send_rate: float, avg_response_time: float):
        """Save current load generation statistics."""
        try:
            stats = {
                'service': 'loadgen',
                'status': 'running',
                'timestamp': time.time(),
                'total_sent': total_sent,
                'total_failed': total_failed,
                'send_rate': send_rate,
                'avg_response_time': avg_response_time,
                'protocols': self.protocols,
                'message_type': self.message_type,
                'message_interval': self.message_interval,
                'device_count': len(self.devices)
            }
            
            async with aiofiles.open('/app/shared/loadgen_stats.json', 'w') as f:
                await f.write(json.dumps(stats, indent=2))
                
        except Exception as e:
            self.logger.error(f"Failed to save load stats: {e}")
    
    def stop_load_generation(self):
        """Stop all load generation."""
        self.logger.info("Stopping load generation...")
        self.running = False
        
        for handler in self.handlers.values():
            handler.stop()
    
    def print_final_stats(self):
        """Print final load generation statistics."""
        total_sent = sum(h.stats.messages_sent for h in self.handlers.values())
        total_failed = sum(h.stats.messages_failed for h in self.handlers.values())
        
        print("\n" + "="*60)
        print("LOAD GENERATION FINAL STATISTICS")
        print("="*60)
        print(f"Total devices: {len(self.devices)}")
        print(f"Protocols used: {', '.join(self.protocols)}")
        print(f"Message type: {self.message_type}")
        print(f"Message interval: {self.message_interval}s")
        print(f"Messages sent: {total_sent}")
        print(f"Messages failed: {total_failed}")
        
        if total_sent + total_failed > 0:
            success_rate = (total_sent / (total_sent + total_failed)) * 100
            print(f"Success rate: {success_rate:.1f}%")
        
        print("\nBy Protocol:")
        for protocol, handler in self.handlers.items():
            if handler.stats.messages_sent > 0 or handler.stats.messages_failed > 0:
                protocol_success_rate = 0
                if handler.stats.messages_sent + handler.stats.messages_failed > 0:
                    protocol_success_rate = (handler.stats.messages_sent / (handler.stats.messages_sent + handler.stats.messages_failed)) * 100
                
                avg_rt = (handler.stats.total_response_time / handler.stats.messages_sent) if handler.stats.messages_sent > 0 else 0
                
                print(f"  {protocol.upper()}: {handler.stats.messages_sent} sent, {handler.stats.messages_failed} failed ({protocol_success_rate:.1f}% success, avg RT: {avg_rt:.3f}s)")
        
        print("="*60)

async def main():
    """Main entry point for the load generator service."""
    loadgen = HonoLoadGenerator()
    
    try:
        # Wait for validator to complete and load device data
        if not await loadgen.wait_for_validator():
            sys.exit(1)
        
        # Start load generation
        success = await loadgen.start_load_generation()
        
        if not success:
            sys.exit(1)
        
    except KeyboardInterrupt:
        loadgen.logger.info("Load generator interrupted")
        loadgen.stop_load_generation()
        loadgen.print_final_stats()
        sys.exit(1)
    except Exception as e:
        loadgen.logger.error(f"Load generator failed: {e}")
        loadgen.stop_load_generation()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
