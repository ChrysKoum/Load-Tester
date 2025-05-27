"""
Reporting module for Hono Load Test Suite.
Handles statistics collection, monitoring, and report generation.
"""

import time
import datetime
import threading
import logging
from pathlib import Path
from typing import Dict, List, Optional

from models.device import Device  # Add this import
from utils.constants import REPORTING_AVAILABLE

if REPORTING_AVAILABLE:
    import matplotlib.pyplot as plt
    import pandas as pd


class ReportingManager:
    """Manages statistics collection and report generation."""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
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
            'msg_rate': [],
            'latency_95th': [],    # Track 95th percentile over time
            'latency_99th': [],    # Track 99th percentile over time
            'avg_latency': []      # Track average latency over time
        }
        
        # Enhanced performance metrics similar to HTTP load testing tools
        self.performance_metrics = {
            'response_times': [],  # Track individual response times
            'response_codes': {},  # Track response codes (200, 500, etc.)
            'latency_history': [], # Sliding window for real-time percentiles
            'latency_sla_violations': {  # Track SLA violations
                '50ms': 0,
                '100ms': 0,
                '200ms': 0,
                '500ms': 0,
                '1000ms': 0
            },
            'data_transferred': {
                'total_bytes': 0,
                'request_bytes': 0,
                'response_bytes': 0,
                'min_message_size': float('inf'),
                'max_message_size': 0
            },
            'protocol_performance': {},  # Per-protocol performance tracking
            'connection_metrics': {      # Connection-level metrics
                'total_connections': 0,
                'failed_connections': 0,
                'connection_times': [],
                'reconnections': 0
            },
            'throughput_history': [],    # Track throughput over time
            'error_patterns': {},        # Track error patterns and timing
            'performance_degradation': {  # Track performance degradation
                'baseline_latency': None,
                'current_latency': None,
                'degradation_percentage': 0
            }
        }
        
        self.protocol_stats = {}  # Track stats per protocol
        self.test_start_time = None
        self.test_end_time = None
        self.running = False
        
        # Advanced metrics configuration
        self.sla_thresholds = {
            'p95_latency_ms': 200,    # 95th percentile should be under 200ms
            'p99_latency_ms': 500,    # 99th percentile should be under 500ms
            'success_rate_percent': 99.5,  # Success rate should be above 99.5%
            'min_throughput_rps': 10  # Minimum acceptable throughput
        }

    def initialize_test(self, protocols: List[str]):
        """Initialize test with specified protocols."""
        self.test_start_time = time.time()
        # Clear the existing dictionary and update it, instead of reassigning
        self.protocol_stats.clear() 
        for protocol in protocols:
            self.protocol_stats[str(protocol).lower()] = {'messages_sent': 0, 'messages_failed': 0, 'devices': 0}
        self.logger.info(f"Test initialized. protocol_stats: {self.protocol_stats} for input protocols: {protocols}")

    def set_running(self, running: bool):
        """Set the running state of the test."""
        self.running = running
        if not running and self.test_start_time:
            self.test_end_time = time.time()

    def generate_report(self, tenants: List[str], devices: List[Device], report_dir: str = "./reports"):
        """Generate detailed test report with charts."""
        import os
        import datetime
        
        # Create reports directory if it doesn't exist
        os.makedirs(report_dir, exist_ok=True)
        
        # Generate timestamp for unique filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(report_dir, f"hono_test_report_{timestamp}.txt")
        
        # Calculate test duration
        if self.test_start_time:
            if self.test_end_time:
                test_duration = self.test_end_time - self.test_start_time
            else:
                test_duration = time.time() - self.test_start_time
        else:
            test_duration = 0
        
        # Generate report content
        report_content = self._generate_report_content(tenants, devices, test_duration)
        
        # Write report to file
        try:
            with open(report_file, 'w') as f:
                f.write(report_content)
            self.logger.info(f"Report saved to: {report_file}")
        except Exception as e:
            self.logger.error(f"Failed to save report: {e}")

    def _generate_report_content(self, tenants: List[str], devices: List[Device], test_duration: float) -> str:
        """Generate the content for the test report."""
        import datetime
        
        total_messages = self.stats['messages_sent'] + self.stats['messages_failed']
        success_rate = (self.stats['messages_sent'] / total_messages * 100) if total_messages > 0 else 0
        avg_rate = self.stats['messages_sent'] / test_duration if test_duration > 0 else 0
        
        devices_per_tenant = len(devices) / len(tenants) if tenants else 0
        validation_rate = (self.stats['validation_success'] / (self.stats['validation_success'] + self.stats['validation_failed']) * 100) if (self.stats['validation_success'] + self.stats['validation_failed']) > 0 else 0
        
        content = f"""============================================================
HONO LOAD TEST DETAILED REPORT
============================================================

Test Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Test Duration: {test_duration:.2f} seconds

CONFIGURATION
----------------------------------------
Registry: {self.config.registry_ip}:{self.config.registry_port}
MQTT Adapter: {self.config.mqtt_adapter_ip}:{self.config.mqtt_adapter_port}
HTTP Adapter: {self.config.http_adapter_ip}:{self.config.http_adapter_port}
MQTT TLS: {self.config.use_mqtt_tls}
HTTP TLS: {self.config.use_tls}

TEST INFRASTRUCTURE
----------------------------------------
Tenants: {len(tenants)}
Devices: {len(devices)}
Devices per Tenant: {devices_per_tenant:.1f}

VALIDATION RESULTS
----------------------------------------
Validation Success: {self.stats['validation_success']}
Validation Failed: {self.stats['validation_failed']}
Validation Rate: {validation_rate:.1f}%

LOAD TEST RESULTS
----------------------------------------
Messages Sent: {self.stats['messages_sent']}
Messages Failed: {self.stats['messages_failed']}
Success Rate: {success_rate:.1f}%
Average Message Rate: {avg_rate:.2f} messages/second

PROTOCOL BREAKDOWN
----------------------------------------"""

        # Add protocol-specific stats
        for protocol, stats in self.protocol_stats.items():
            protocol_total = stats['messages_sent'] + stats['messages_failed']
            protocol_success_rate = (stats['messages_sent'] / protocol_total * 100) if protocol_total > 0 else 100.0
            
            content += f"""
Protocol: {protocol.upper()}
  Devices: {stats['devices']}
  Messages Sent: {stats['messages_sent']}
  Messages Failed: {stats['messages_failed']}
  Success Rate: {protocol_success_rate:.1f}%"""

        content += f"""

============================================================
Report generated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

        return content

    def print_enhanced_final_stats(self):
        """Print enhanced final statistics."""
        if not self.test_start_time:
            print("❌ No test data available")
            return

        test_duration = (self.test_end_time or time.time()) - self.test_start_time
        total_messages = self.stats['messages_sent'] + self.stats['messages_failed']
        success_rate = (self.stats['messages_sent'] / total_messages * 100) if total_messages > 0 else 0
        avg_rate = self.stats['messages_sent'] / test_duration if test_duration > 0 else 0

        print("\n" + "="*60)
        print("📊 ENHANCED LOAD TEST RESULTS")
        print("="*60)
        print(f"⏱️  Test Duration: {test_duration:.2f} seconds")
        print(f"📤 Messages Sent: {self.stats['messages_sent']}")
        print(f"❌ Messages Failed: {self.stats['messages_failed']}")
        print(f"✅ Success Rate: {success_rate:.1f}%")
        print(f"📈 Average Rate: {avg_rate:.2f} msg/sec")
        
        # Protocol breakdown
        if self.protocol_stats:
            print(f"\n📋 Protocol Breakdown:")
            for protocol, stats in self.protocol_stats.items():
                protocol_total = stats['messages_sent'] + stats['messages_failed']
                protocol_success = (stats['messages_sent'] / protocol_total * 100) if protocol_total > 0 else 100.0
                print(f"   {protocol.upper()}: {stats['messages_sent']}/{protocol_total} ({protocol_success:.1f}%)")

        print("="*60)

    def print_final_stats(self):
        """Print final statistics."""
        self.print_enhanced_final_stats()
        # if hasattr(self, 'print_advanced_findings'): # This can be added back if print_advanced_findings is implemented

    def record_latency_metrics(self, response_time_ms: float):
        """Record latency metrics and check SLA violations."""
        self.performance_metrics['response_times'].append(response_time_ms)
        # Use a sliding window for real-time percentile calculation if needed
        self.performance_metrics['latency_history'].append(response_time_ms)
        if len(self.performance_metrics['latency_history']) > 1000: # Keep last 1000 for sliding window
            self.performance_metrics['latency_history'].pop(0)

        # Track SLA violations based on defined thresholds
        if response_time_ms > self.sla_thresholds.get('p99_latency_ms', 1000): # Default to 1000ms if not set
            self.performance_metrics['latency_sla_violations']['1000ms'] += 1 # Or use a dynamic key based on SLA
        elif response_time_ms > self.sla_thresholds.get('p95_latency_ms', 500): # Default to 500ms
             self.performance_metrics['latency_sla_violations']['500ms'] += 1
        # Add more granular SLA checks if needed
        elif response_time_ms > 200:
            self.performance_metrics['latency_sla_violations']['200ms'] += 1
        elif response_time_ms > 100:
            self.performance_metrics['latency_sla_violations']['100ms'] += 1
        elif response_time_ms > 50:
            self.performance_metrics['latency_sla_violations']['50ms'] += 1
        
        # Potentially update performance degradation metrics here
        # For example, compare current_latency (e.g., avg of last N) to baseline_latency

    def calculate_percentiles(self, data_list: List[float], percentiles_to_calc: List[float] = None) -> Dict[str, float]:
        """Calculate various percentiles from a data list."""
        if not data_list:
            return {}
        
        if percentiles_to_calc is None:
            percentiles_to_calc = [50, 90, 95, 99, 99.9]
            
        sorted_data = sorted(data_list)
        length = len(sorted_data)
        
        calculated_percentiles = {}
        for p in percentiles_to_calc:
            if not (0 < p <= 100):
                self.logger.warning(f"Invalid percentile requested: {p}. Skipping.")
                continue
            index = int((p / 100.0) * (length -1)) # Corrected index calculation for 0-based list
            calculated_percentiles[f'p{p}'] = sorted_data[index]
        
        return calculated_percentiles

    def get_real_time_latency_stats(self) -> Optional[Dict]:
        """Get real-time latency statistics from the latency_history."""
        if not self.performance_metrics['latency_history']:
            return None
        
        recent_latencies = self.performance_metrics['latency_history'] # Use the whole history or a recent slice
        if not recent_latencies: # Double check if history became empty
            return None

        percentiles = self.calculate_percentiles(recent_latencies)
        
        return {
            'current_avg': sum(recent_latencies) / len(recent_latencies),
            'current_min': min(recent_latencies),
            'current_max': max(recent_latencies),
            'percentiles': percentiles,
            'sample_size': len(recent_latencies)
        }

    def record_message_metrics(self, protocol: str, response_time_ms: float, status_code: int, message_size_bytes: int = 0, success: bool = True):
        """Record comprehensive metrics for a message attempt."""
        if success:
            self.record_message_sent(protocol)
        else:
            self.record_message_failed(protocol)

        self.record_latency_metrics(response_time_ms) # Assumes record_latency_metrics exists and takes response_time_ms

        # Record status code
        self.performance_metrics['response_codes'][status_code] = self.performance_metrics['response_codes'].get(status_code, 0) + 1

        # Record data transferred
        if message_size_bytes > 0:
            self.performance_metrics['data_transferred']['total_bytes'] += message_size_bytes
            # Assuming request/response distinction might be added later or is part of message_size_bytes
            if success: # Simplistic: count towards request if successful, could be more nuanced
                 self.performance_metrics['data_transferred']['request_bytes'] += message_size_bytes
            
            self.performance_metrics['data_transferred']['min_message_size'] = min(
                self.performance_metrics['data_transferred']['min_message_size'], message_size_bytes
            )
            self.performance_metrics['data_transferred']['max_message_size'] = max(
                self.performance_metrics['data_transferred']['max_message_size'], message_size_bytes
            )
        
        # Per-protocol performance (can be expanded)
        if protocol not in self.performance_metrics['protocol_performance']:
            self.performance_metrics['protocol_performance'][protocol] = {
                'latencies': [],
                'status_codes': {}
            }
        self.performance_metrics['protocol_performance'][protocol]['latencies'].append(response_time_ms)
        self.performance_metrics['protocol_performance'][protocol]['status_codes'][status_code] = \
            self.performance_metrics['protocol_performance'][protocol]['status_codes'].get(status_code, 0) + 1

    def record_message_sent(self, protocol: str):
        """Record a successful message send."""
        self.stats['messages_sent'] += 1
        if protocol in self.protocol_stats:
            self.protocol_stats[protocol]['messages_sent'] += 1

    def record_message_failed(self, protocol: str):
        """Record a failed message send."""
        self.stats['messages_failed'] += 1
        if protocol in self.protocol_stats:
            self.protocol_stats[protocol]['messages_failed'] += 1

    def monitor_stats(self):
        """Monitor and print statistics during load testing."""
        def stats_monitor():
            last_sent = 0
            last_failed = 0 # Track last failed to calculate rate of failures too
            last_time = time.time()
            
            while self.running:
                time.sleep(10)  # Print stats every 10 seconds
                if not self.running: # Check again after sleep, in case test stopped
                    break

                current_time = time.time()
                current_sent_total = self.stats['messages_sent']
                current_failed_total = self.stats['messages_failed']
                
                elapsed = current_time - last_time
                if elapsed <= 0: # Avoid division by zero if time hasn't advanced
                    elapsed = 1 # Assume 1 second to prevent error, or skip update

                # Calculate message rate for this interval
                interval_sent = current_sent_total - last_sent
                interval_failed = current_failed_total - last_failed
                
                sent_rate = interval_sent / elapsed
                failed_rate = interval_failed / elapsed
                
                # Get real-time latency stats
                latency_stats_dict = self.get_real_time_latency_stats()
                
                # Store time series data for reporting
                self.time_series_data['timestamps'].append(datetime.datetime.now())
                self.time_series_data['messages_sent'].append(current_sent_total) # Store cumulative
                self.time_series_data['messages_failed'].append(current_failed_total) # Store cumulative
                self.time_series_data['msg_rate'].append(sent_rate) # Store interval rate
                
                latency_info_str = ""
                if latency_stats_dict:
                    self.time_series_data['avg_latency'].append(latency_stats_dict.get('current_avg', 0))
                    self.time_series_data['latency_95th'].append(latency_stats_dict.get('percentiles', {}).get('p95', 0))
                    self.time_series_data['latency_99th'].append(latency_stats_dict.get('percentiles', {}).get('p99', 0))
                    latency_info_str = (f", Avg Lat: {latency_stats_dict.get('current_avg', 0):.1f}ms, "
                                        f"P95: {latency_stats_dict.get('percentiles', {}).get('p95', 0):.1f}ms, "
                                        f"P99: {latency_stats_dict.get('percentiles', {}).get('p99', 0):.1f}ms")
                else:
                    self.time_series_data['avg_latency'].append(0)
                    self.time_series_data['latency_95th'].append(0)
                    self.time_series_data['latency_99th'].append(0)
                
                self.logger.info(
                    f"Stats - Sent: {current_sent_total} ({sent_rate:.1f}/s), "
                    f"Failed: {current_failed_total} ({failed_rate:.1f}/s)"
                    f"{latency_info_str}"
                )
                
                # Update for next interval
                last_sent = current_sent_total
                last_failed = current_failed_total
                last_time = current_time
        
        # Ensure the thread is only started if it's not already running or if it's properly managed
        # For simplicity, assuming it's started once per test run.
        # If monitor_stats can be called multiple times, thread management needs to be more robust.
        stats_thread = threading.Thread(target=stats_monitor, name="StatsMonitorThread")
        stats_thread.daemon = True # Ensure thread doesn't block program exit
        stats_thread.start()
