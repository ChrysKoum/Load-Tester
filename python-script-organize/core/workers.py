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
import socket # Keep for specific exceptions like socket.timeout
from typing import Dict, Optional # Added Optional for type hinting

from models.device import Device
from config.hono_config import HonoConfig


class ProtocolWorkers:
    """Contains worker functions for different protocols."""
    
    def __init__(self, config: HonoConfig, shared_stats: Dict, protocol_stats: Dict, reporting_manager=None):
        self.config = config
        self.shared_stats = shared_stats
        self.protocol_stats = protocol_stats
        self.reporting_manager = reporting_manager
        self.running = False
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def set_running(self, running: bool):
        """Set the running state for all workers."""
        self.running = running

    def _update_stats(self, protocol_key: str, success: bool, message_count_increment: int = 1):
        """Helper to update general and protocol-specific stats."""
        if success:
            self.stats['messages_sent'] += message_count_increment
            self.protocol_stats[protocol_key]['messages_sent'] += message_count_increment
        else:
            self.stats['messages_failed'] += message_count_increment # Assuming one failure means one message attempt failed
            self.protocol_stats[protocol_key]['messages_failed'] += message_count_increment

    def _get_mqtt_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Creates and configures an SSLContext for MQTT TLS connections."""
        if not self.config.use_mqtt_tls:
            return None

        try:
            # PROTOCOL_TLS_CLIENT is a good default, requires Python 3.6+
            # It automatically chooses the highest protocol version that both client and server support,
            # and enables hostname checking and certificate validation by default.
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.minimum_version = ssl.TLSVersion.TLSv1_2 # Enforce TLSv1.2 or higher

            if self.config.ca_file_path and os.path.exists(self.config.ca_file_path):
                context.load_verify_locations(cafile=self.config.ca_file_path)
                context.verify_mode = ssl.CERT_REQUIRED
                context.check_hostname = True # Explicitly ensure hostname checking
                self.logger.debug(f"MQTT SSLContext: Loaded CA file '{self.config.ca_file_path}'. Server certificate will be verified.")
            elif self.config.mqtt_allow_system_cas: # New config option
                # Uses system's trusted CAs. Hostname checking and cert validation are on by default.
                self.logger.debug("MQTT SSLContext: Using system's default CA certificates. Server certificate will be verified.")
            elif self.config.mqtt_allow_insecure_tls: # New config option for explicitly allowing insecure
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                self.logger.warning("MQTT SSLContext: Insecure TLS connection. Server certificate WILL NOT be verified. THIS IS NOT RECOMMENDED FOR PRODUCTION.")
            else:
                # Default secure: if use_mqtt_tls is True but no CA is provided and system CAs are not explicitly allowed,
                # this will likely fail unless the server cert is issued by a public CA already in the default trust store.
                # Or, raise an error if a stricter policy is desired when no CA is specified.
                self.logger.warning("MQTT SSLContext: TLS enabled but no CA file specified and system CAs not explicitly allowed. Relying on default trust store. Verification might fail if server uses a private CA.")
            return context
        except ssl.SSLError as e:
            self.logger.error(f"MQTT SSLContext: Failed to create/load SSL context: {e}. MQTT TLS connection will likely fail.")
            return None # Or raise an exception to prevent insecure connection attempt
        except FileNotFoundError:
            self.logger.error(f"MQTT SSLContext: CA file not found at '{self.config.ca_file_path}'. MQTT TLS connection will likely fail.")
            return None # Or raise


    def mqtt_telemetry_worker(self, device: Device, message_interval: float, protocol_name: str = "telemetry"):
        """Worker function for MQTT telemetry publishing."""
        mqtt_protocol_key = 'mqtt' # For stats
        if mqtt_protocol_key not in self.protocol_stats:
            self.logger.error("MQTT protocol stats not initialized!")
            return
        self.protocol_stats[mqtt_protocol_key]['devices'] += 1

        client = mqtt.Client(client_id=device.device_id) # Using device_id as client_id
        client.username_pw_set(f"{device.auth_id}@{device.tenant_id}", device.password)

        mqtt_host = self.config.mqtt_adapter_ip
        ssl_context_obj = self._get_mqtt_ssl_context()

        if self.config.use_mqtt_tls:
            mqtt_port = self.config.mqtt_adapter_port
            if ssl_context_obj:
                client.tls_set_context(ssl_context_obj)
                self.logger.debug(f"Device {device.device_id}: Attempting MQTT TLS to {mqtt_host}:{mqtt_port}")
            else:
                self.logger.error(f"Device {device.device_id}: MQTT TLS requested but SSL context creation failed. Aborting connection.")
                self._update_stats(mqtt_protocol_key, success=False)
                return
        else:
            mqtt_port = self.config.mqtt_insecure_port
            self.logger.debug(f"Device {device.device_id}: Attempting MQTT Insecure to {mqtt_host}:{mqtt_port}")

        connected_flag = False # Using a more descriptive name
        connection_rc_detail = None # Store return code string from on_connect

        # --- Nested Callbacks ---
        def on_connect(client_instance, userdata, flags, rc):
            nonlocal connected_flag, connection_rc_detail
            if rc == mqtt.MQTT_ERR_SUCCESS:
                connected_flag = True
                self.logger.debug(f"MQTT connected for device {device.device_id}")
            else:
                # Error will be logged by the main connection logic after timeout/failure
                connection_rc_detail = mqtt.connack_string(rc)
                self.logger.debug(f"MQTT on_connect callback failed for device {device.device_id}: {connection_rc_detail} (rc: {rc})")

        def on_disconnect(client_instance, userdata, rc):
            nonlocal connected_flag
            # Only log if it's an unexpected disconnect
            if rc != mqtt.MQTT_ERR_SUCCESS and connected_flag: # Check connected_flag to avoid logging after explicit disconnect
                self.logger.warning(f"MQTT unexpected disconnection for device {device.device_id}, rc: {mqtt.error_string(rc)} ({rc})")
            else:
                self.logger.debug(f"MQTT disconnected for device {device.device_id}, rc: {rc}")
            connected_flag = False
        # --- End Nested Callbacks ---

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect

        try:
            client.connect(mqtt_host, mqtt_port, self.config.mqtt_keepalive)
            client.loop_start()

            # Wait for the on_connect callback to fire with a timeout
            connect_timeout = self.config.mqtt_connect_timeout # Use a configured timeout
            wait_start_time = time.monotonic()
            while not connected_flag and (time.monotonic() - wait_start_time) < connect_timeout:
                if connection_rc_detail: # on_connect reported an error, no need to wait further
                    break
                time.sleep(0.05) # Short sleep to yield execution

            if not connected_flag:
                err_msg = connection_rc_detail or f"Connection attempt timed out after {connect_timeout}s"
                self.logger.error(f"MQTT final connection status for {device.device_id}: FAILED - {err_msg}")
                self._update_stats(mqtt_protocol_key, success=False)
                # client.loop_stop() is in finally
                return

            # If connected
            message_count = 0
            while self.running and connected_flag: # Check connected_flag in case of unexpected disconnect
                payload_data = {
                    "device_id": device.device_id, "tenant_id": device.tenant_id, "timestamp": int(time.time()),
                    "message_count": message_count, "protocol": "mqtt",
                    "temperature": round(random.uniform(18.0, 35.0), 2), "humidity": round(random.uniform(30.0, 90.0), 2),
                    "pressure": round(random.uniform(980.0, 1030.0), 2), "battery": round(random.uniform(20.0, 100.0), 2),
                    "signal_strength": random.randint(-100, -30)
                }
                payload_json = json.dumps(payload_data)
                message_size_bytes = len(payload_json.encode('utf-8'))

                topic = protocol_name # e.g., "telemetry" or "event"
                qos = 0 if protocol_name == "telemetry" else 1 # Example QoS handling

                start_time = time.monotonic()
                msg_info = client.publish(topic, payload_json, qos=qos)
                # For QoS 0, publish() returns immediately. For QoS 1/2, need to wait for PUBACK/PUBCOMP
                # For simplicity in a load test, we might not wait for PUBACK for QoS 1 if measuring raw publish rate.
                # If acknowledgment is critical, msg_info.wait_for_publish(timeout) would be needed.
                # Let's assume publish time is sufficient for this example.
                end_time = time.monotonic()
                response_time_ms = (end_time - start_time) * 1000

                if msg_info.rc == mqtt.MQTT_ERR_SUCCESS:
                    if self.reporting_manager:
                        self.reporting_manager.record_message_sent("mqtt")
                        # Record latency metrics if available
                        if 'response_time_ms' in locals():
                            self.reporting_manager.record_latency_metrics(response_time_ms)
                    else:
                        self.shared_stats['messages_sent'] += 1
                    message_count += 1
                    self.logger.debug(f"MQTT message {message_count} sent by {device.device_id} to topic '{topic}' in {response_time_ms:.0f}ms")
                else:
                    if self.reporting_manager:
                        self.reporting_manager.record_message_failed("mqtt")
                    else:
                        self.shared_stats['messages_failed'] += 1
                    self.logger.warning(f"MQTT publish failed for device {device.device_id}: {mqtt.error_string(msg_info.rc)} (rc: {msg_info.rc})")
                    self._update_stats(mqtt_protocol_key, success=False)
                    # Decide if to break loop on publish failure or continue
                    # if not msg_info.is_published(): # Additional check for QoS 1/2 if not waiting
                    #     self.logger.warning(f"MQTT message for {device.device_id} may not have been sent (mid={msg_info.mid})")

                if not self.running or not connected_flag: # Re-check running and connection status before sleep
                    break
                time.sleep(message_interval)

        except (socket.timeout, TimeoutError) as e: # Catch generic TimeoutError too
            self.logger.error(f"MQTT worker timeout for {device.device_id}: {e}")
            self._update_stats(mqtt_protocol_key, success=False)
        except ConnectionRefusedError as e:
            self.logger.error(f"MQTT worker ConnectionRefusedError for {device.device_id}: {e}")
            self._update_stats(mqtt_protocol_key, success=False)
        except OSError as e: # Catches NoRouteToHost, HostDown, etc.
            self.logger.error(f"MQTT worker OSError for {device.device_id}: {e}")
            self._update_stats(mqtt_protocol_key, success=False)
        except Exception as e:
            self.logger.exception(f"MQTT worker generic error for device {device.device_id}: {e.__class__.__name__} - {e}") # Use .exception for stack trace
            self._update_stats(mqtt_protocol_key, success=False)
        finally:
            try:
                if client.is_connected(): # is_connected() might not be fully reliable after loop_stop
                    client.disconnect()
                client.loop_stop(force=False) # Allow pending messages to clear if possible
                self.logger.debug(f"MQTT client resources released for device {device.device_id}")
            except Exception as e_finally:
                self.logger.error(f"Error during MQTT worker cleanup for {device.device_id}: {e_finally}")

    async def _get_http_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Creates and configures an SSLContext for HTTP/HTTPS connections."""
        if not self.config.use_tls: # Assuming a general 'use_tls' for HTTP, or could be 'use_http_tls'
            return None
        try:
            if self.config.ca_file_path and os.path.exists(self.config.ca_file_path):
                context = ssl.create_default_context(cafile=self.config.ca_file_path)
                self.logger.debug(f"HTTP SSLContext: Loaded CA file '{self.config.ca_file_path}'.")
            else:
                # Uses system's trusted CAs
                context = ssl.create_default_context()
                self.logger.debug("HTTP SSLContext: Using system's default CA certificates.")

            if not self.config.verify_ssl: # If explicitely set to not verify (e.g. for self-signed certs in dev)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                self.logger.warning("HTTP SSLContext: SSL verification disabled. Server certificate WILL NOT be verified. NOT RECOMMENDED FOR PRODUCTION.")
            else:
                context.check_hostname = True
                context.verify_mode = ssl.CERT_REQUIRED

            context.minimum_version = ssl.TLSVersion.TLSv1_2
            return context
        except ssl.SSLError as e:
            self.logger.error(f"HTTP SSLContext: Failed to create/load SSL context: {e}. HTTPS connection will likely fail.")
            return None
        except FileNotFoundError:
            self.logger.error(f"HTTP SSLContext: CA file not found at '{self.config.ca_file_path}'. HTTPS connection will likely fail.")
            return None


    async def http_telemetry_worker(self, device: Device, message_interval: float, protocol_name: str = "telemetry"): # Renamed 'protocol' to 'protocol_name'
        """Worker function for HTTP telemetry publishing."""
        http_protocol_key = 'http' # For stats
        self.protocol_stats[http_protocol_key]['devices'] += 1

        ssl_context = await self._get_http_ssl_context() # Make it async if it ever needs async ops

        # Determine scheme and port based on TLS configuration
        if self.config.use_tls: # General TLS config, or specific self.config.use_http_tls
            protocol_scheme = "https"
            port = self.config.http_adapter_port # Assuming this is the TLS port for HTTP adapter
        else:
            protocol_scheme = "http"
            port = self.config.http_insecure_port # Assuming this is the non-TLS port

        url = f"{protocol_scheme}://{self.config.http_adapter_ip}:{port}/{protocol_name}" # Use protocol_name for path

        connector = aiohttp.TCPConnector(ssl=ssl_context if self.config.use_tls else False) # Pass False if not using TLS
        timeout_config = aiohttp.ClientTimeout(total=self.config.http_timeout)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout_config) as session:
            headers = {"Content-Type": "application/json"}
            # Ensure auth_id is used for HTTP Basic Auth username part
            auth = aiohttp.BasicAuth(f"{device.auth_id}@{device.tenant_id}", device.password)

            message_count = 0
            while self.running:
                payload_data = {
                    "device_id": device.device_id, "tenant_id": device.tenant_id, "timestamp": int(time.time()),
                    "message_count": message_count, "protocol": "http",
                    "temperature": round(random.uniform(18.0, 35.0), 2), "humidity": round(random.uniform(30.0, 90.0), 2),
                    "pressure": round(random.uniform(980.0, 1030.0), 2), "battery": round(random.uniform(20.0, 100.0), 2),
                    "signal_strength": random.randint(-100, -30)
                }
                payload_json_str = json.dumps(payload_data)
                message_size_bytes = len(payload_json_str.encode('utf-8'))

                start_time = time.monotonic()
                response_status_code = 500 # Default to error

                try:
                    async with session.post(url, data=payload_json_str, headers=headers, auth=auth) as response:
                        end_time = time.monotonic()
                        response_time_ms = (end_time - start_time) * 1000
                        response_status_code = response.status

                        if self.reporting_manager:
                            self.reporting_manager.record_message_metrics(
                                protocol=http_protocol_key,
                                response_time_ms=response_time_ms,
                                status_code=response.status,
                                message_size_bytes=len(payload_json_str.encode('utf-8')), # Corrected variable here
                                success=True
                            )
                            self.logger.debug(f"HTTP success for {device.device_id}: {response.status}, {response_time_ms:.2f}ms")
                        else: # Fallback if reporting_manager is somehow not available
                            self.shared_stats['messages_sent'] += 1
                            if http_protocol_key in self.protocol_stats:
                                self.protocol_stats[http_protocol_key]['messages_sent'] += 1
                        
                        # Optionally read response content if needed, e.g., for validation
                        # response_text = await response.text() 
                        # self.logger.debug(f"HTTP Response for {device.device_id}: {response_text[:100]}")


                    if response.status >= 400:
                        self.logger.warning(f"HTTP error for device {device.device_id}: {response.status}")
                        if self.reporting_manager:
                            # This path might be redundant if record_message_metrics handles success=False
                            # but kept for clarity if record_message_metrics is only called on successful HTTP transaction
                            self.reporting_manager.record_message_failed(http_protocol_key)
                        else:
                            self.shared_stats['messages_failed'] += 1
                            if http_protocol_key in self.protocol_stats:
                                 self.protocol_stats[http_protocol_key]['messages_failed'] += 1
                
                except aiohttp.ClientConnectorError as e:
                    end_time = time.monotonic()
                    response_time_ms = (end_time - start_time) * 1000
                    self.logger.error(f"HTTP connection error for device {device.device_id}: {e}")
                    if self.reporting_manager:
                        self.reporting_manager.record_message_metrics(
                            protocol=http_protocol_key,
                            response_time_ms=response_time_ms,
                            status_code=599, # Custom code for connection error
                            message_size_bytes=message_size_bytes,
                            success=False
                        )
                    else:
                        self.shared_stats['messages_failed'] += 1
                        if http_protocol_key in self.protocol_stats:
                            self.protocol_stats[http_protocol_key]['messages_failed'] += 1
                
                except asyncio.TimeoutError:
                    end_time = time.monotonic()
                    response_time_ms = (end_time - start_time) * 1000
                    self.logger.warning(f"HTTP timeout for device {device.device_id}")
                    if self.reporting_manager:
                        self.reporting_manager.record_message_metrics(
                            protocol=http_protocol_key,
                            response_time_ms=response_time_ms, # or a fixed high value for timeout
                            status_code=408, # HTTP Timeout
                            message_size_bytes=message_size_bytes,
                            success=False
                        )
                    else:
                        self.shared_stats['messages_failed'] += 1
                        if http_protocol_key in self.protocol_stats:
                            self.protocol_stats[http_protocol_key]['messages_failed'] += 1

                except Exception as e:
                    end_time = time.monotonic()
                    response_time_ms = (end_time - start_time) * 1000
                    self.logger.error(f"HTTP general error for device {device.device_id}: {e}", exc_info=True)
                    if self.reporting_manager:
                         self.reporting_manager.record_message_metrics(
                            protocol=http_protocol_key,
                            response_time_ms=response_time_ms,
                            status_code=598, # Custom code for other client-side error
                            message_size_bytes=message_size_bytes,
                            success=False
                        )
                    else:
                        self.shared_stats['messages_failed'] += 1
                        if http_protocol_key in self.protocol_stats:
                            self.protocol_stats[http_protocol_key]['messages_failed'] += 1

                await asyncio.sleep(message_interval)