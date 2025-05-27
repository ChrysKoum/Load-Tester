"""
Protocol workers module for Hono Load Test Suite.
Contains worker functions for different protocols (MQTT, HTTP, etc.).
"""

import os
import ssl
import json
import time
import random
import logging
import asyncio
import aiohttp
import paho.mqtt.client as mqtt
import socket
from typing import Dict

from models.device import Device
from config.hono_config import HonoConfig


class ProtocolWorkers:
    """Contains worker functions for different protocols."""
    
    def __init__(self, config: HonoConfig, stats: Dict, protocol_stats: Dict):
        self.config = config
        self.stats = stats
        self.protocol_stats = protocol_stats
        self.running = False
        self.logger = logging.getLogger(__name__)
    
    def set_running(self, running: bool):
        """Set the running state for all workers."""
        self.running = running
        
    def mqtt_telemetry_worker(self, device: Device, message_interval: float, protocol_name: str = "telemetry"): # Renamed 'protocol' to 'protocol_name' to avoid conflict
        """Worker function for MQTT telemetry publishing."""
        if 'mqtt' not in self.protocol_stats:
            self.logger.error("MQTT protocol stats not initialized!")
            return
        self.protocol_stats['mqtt']['devices'] += 1
        
        client = mqtt.Client()
        client.username_pw_set(f"{device.auth_id}@{device.tenant_id}", device.password)
        
        mqtt_port = self.config.mqtt_adapter_port
        if self.config.use_mqtt_tls:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False 
            context.verify_mode = ssl.CERT_NONE

            if self.config.ca_file_path and os.path.exists(self.config.ca_file_path):
                try:
                    context.load_verify_locations(cafile=self.config.ca_file_path)
                    self.logger.debug(f"SSLContext: Loaded CA file for context: {self.config.ca_file_path}")
                except ssl.SSLError as e:
                    self.logger.error(f"SSLContext: Failed to load CA file '{self.config.ca_file_path}': {e}. Proceeding without it.")
                except FileNotFoundError:
                    self.logger.error(f"SSLContext: CA file not found at '{self.config.ca_file_path}'. Proceeding without it.")
            else:
                self.logger.debug("SSLContext: No explicit CA file. Validation disabled (CERT_NONE).")
            
            client.tls_set_context(context)
            self.logger.debug(f"Using MQTT TLS on port {mqtt_port} with custom SSLContext.")
        else:
            mqtt_port = self.config.mqtt_insecure_port
            self.logger.debug(f"Using MQTT insecure on port {mqtt_port}")
        
        connected = False
        connection_error_detail = None
        
        def on_connect(client, userdata, flags, rc):
            nonlocal connected, connection_error_detail
            if rc == 0:
                connected = True
                self.logger.debug(f"MQTT connected for device {device.device_id}")
            else:
                connection_error_detail = mqtt.connack_string(rc)
                self.logger.error(f"MQTT on_connect failed for device {device.device_id}: {connection_error_detail} (rc: {rc})")
                # Failure is handled after connect attempt loop

        def on_disconnect(client, userdata, rc):
            nonlocal connected
            if rc != 0: # Unexpected disconnect
                self.logger.warning(f"MQTT unexpected disconnection for device {device.device_id}, rc: {rc}")
            connected = False

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        
        try:
            self.logger.debug(f"Attempting MQTT connection for {device.device_id} to {self.config.mqtt_adapter_ip}:{mqtt_port}")
            client.connect(self.config.mqtt_adapter_ip, mqtt_port, self.config.mqtt_keepalive)
            client.loop_start()
            
            connect_loop_start_time = time.time()
            while not connected and (time.time() - connect_loop_start_time) < (self.config.mqtt_keepalive / 2 or 10): # Wait for on_connect
                if connection_error_detail: # on_connect reported an error
                    break 
                time.sleep(0.1)
            
            if not connected:
                err_msg = connection_error_detail or "Connection attempt timed out before on_connect"
                self.logger.error(f"MQTT connection failed for device {device.device_id}: {err_msg}")
                self.stats['messages_failed'] += 1
                self.protocol_stats['mqtt']['messages_failed'] += 1
                client.loop_stop() # Ensure loop is stopped
                return

            message_count = 0
            while self.running and connected:
                payload_data = {
                    "device_id": device.device_id, "tenant_id": device.tenant_id, "timestamp": int(time.time()),
                    "message_count": message_count, "protocol": "mqtt",
                    "temperature": round(random.uniform(18.0, 35.0), 2), "humidity": round(random.uniform(30.0, 90.0), 2),
                    "pressure": round(random.uniform(980.0, 1030.0), 2), "battery": round(random.uniform(20.0, 100.0), 2),
                    "signal_strength": random.randint(-100, -30)
                }
                
                topic = protocol_name
                qos = 0 if protocol_name == "telemetry" else 1
                
                result = client.publish(topic, json.dumps(payload_data), qos=qos)
                
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    self.stats['messages_sent'] += 1
                    self.protocol_stats['mqtt']['messages_sent'] += 1
                    message_count += 1
                    self.logger.debug(f"MQTT message {message_count} sent by {device.device_id}")
                else:
                    self.logger.warning(f"MQTT publish failed for device {device.device_id}: {mqtt.error_string(result.rc)} (rc: {result.rc})")
                    self.stats['messages_failed'] += 1
                    self.protocol_stats['mqtt']['messages_failed'] += 1
                
                time.sleep(message_interval)
        
        except socket.timeout:
            self.logger.error(f"MQTT worker error for device {device.device_id}: socket.timeout during connect/operation")
            self.stats['messages_failed'] += 1
            self.protocol_stats['mqtt']['messages_failed'] += 1
        except ConnectionRefusedError:
            self.logger.error(f"MQTT worker error for device {device.device_id}: ConnectionRefusedError")
            self.stats['messages_failed'] += 1
            self.protocol_stats['mqtt']['messages_failed'] += 1
        except OSError as e: # Catches NoRouteToHost, HostDown, etc.
            self.logger.error(f"MQTT worker OSError for device {device.device_id}: {e}")
            self.stats['messages_failed'] += 1
            self.protocol_stats['mqtt']['messages_failed'] += 1
        except Exception as e:
            # This will catch other errors, including if str(e) was "timed out" from a generic timeout
            self.logger.error(f"MQTT worker generic error for device {device.device_id}: {e.__class__.__name__} - {e}")
            self.stats['messages_failed'] += 1
            self.protocol_stats['mqtt']['messages_failed'] += 1
        finally:
            try:
                if client.is_connected():
                    client.disconnect()
                client.loop_stop()
                self.logger.debug(f"MQTT client disconnected and loop stopped for device {device.device_id}")
            except Exception as e_finally:
                self.logger.error(f"Error during MQTT worker cleanup for {device.device_id}: {e_finally}")

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
