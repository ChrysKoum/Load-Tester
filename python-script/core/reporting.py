"""
Enhanced Reporting module for Hono Load Test Suite.
Adds registration throttling and Poisson distribution metrics.
"""

import time
import datetime
import threading
import logging
import random
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING

# Import HonoConfig only for type checking to avoid circular imports at runtime
if TYPE_CHECKING:
    from config.hono_config import HonoConfig # Import for type hinting

from models.device import Device
from utils.constants import REPORTING_AVAILABLE # Ensure this is imported

if REPORTING_AVAILABLE:
    import matplotlib
    # It's good practice to set the backend *before* importing pyplot if possible,
    # or at least before any plotting commands.
    try:
        # Attempt to use a non-interactive backend suitable for scripts
        matplotlib.use('Agg')
    except ImportError: # Fallback if 'Agg' is not available (e.g. minimal install)
        pass
    except Exception as e:
        # Log a warning if backend switching fails for other reasons.
        # This logging will happen if the logger for this module is already configured.
        # logging.getLogger(__name__).warning(f"Could not set matplotlib backend to Agg: {e}")
        pass
    import matplotlib.pyplot as plt
    import pandas as pd
else:
    # If matplotlib or pandas are not available, plotting will be skipped.
    # The REPORTING_AVAILABLE flag will control this.
    pass


@dataclass
class AdvancedMetrics:
    """Advanced metrics for sophisticated load testing."""
    registration_delays: List[float]  # Track registration delays
    registration_queue_size: int      # Current registration queue size
    poisson_intervals: List[float]    # Track actual intervals used
    expected_vs_actual_rate: Dict[str, float]  # Rate comparison
    adapter_load_metrics: Dict[str, Any]  # Track adapter load (changed int to Any for flexibility)
    message_distribution_stats: Dict[str, float]  # Distribution statistics


class ReportingManager:
    """Enhanced reporting manager with advanced load testing metrics."""

    def __init__(self, config: 'HonoConfig'): # Forward reference 'HonoConfig' is fine with TYPE_CHECKING
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Basic stats
        self.stats = {
            'messages_sent': 0,
            'messages_failed': 0,
            'devices_registered': 0,
            'tenants_registered': 0,
            'validation_success': 0,
            'validation_failed': 0,
            'registration_attempts': 0,
            'registration_throttled': 0
        }
        
        # Time series data
        self.time_series_data = {
            'timestamps': [],
            'messages_sent': [],
            'messages_failed': [],
            'msg_rate': [],
            'latency_95th': [],
            'latency_99th': [],
            'avg_latency': [],
            'registration_rate': [],        # Track registration rate over time
            'actual_msg_intervals': [],     # Track actual message intervals
            'adapter_load': []              # Track adapter load over time
        }
        
        # Enhanced performance metrics
        self.performance_metrics: Dict[str, Any] = {
            'messages_sent': 0,
            'messages_failed': 0,
            'response_times': [],
            'protocol_stats': {}, 
            'validation_success': 0, 
            'validation_failed': 0,  
            'total_validated_devices': 0,
            'latency_history': [], # For get_real_time_latency_stats
            'latency_sla_violations': { # For record_latency_metrics
                '50ms': 0, '100ms': 0, '200ms': 0, '500ms': 0, '1000ms': 0 
            },
            'response_codes': {}, # For record_message_metrics
            'data_transferred': { # For record_message_metrics
                'total_bytes': 0, 'request_bytes': 0, 
                'min_message_size': float('inf'), 'max_message_size': 0
            },
            'protocol_performance': {} # For record_message_metrics
        }
        
        # NEW: Advanced metrics for registration throttling and Poisson distribution
        self.advanced_metrics = AdvancedMetrics(
            registration_delays=[],
            registration_queue_size=0,
            poisson_intervals=[],
            expected_vs_actual_rate={},
            adapter_load_metrics={
                'current_load': 0,
                'peak_load': 0,
                'avg_load': 0,
                'load_samples': []
            },
            message_distribution_stats={
                'mean_interval': 0,
                'variance': 0,
                'coefficient_of_variation': 0,
                'actual_lambda': 0
            }
        )
        
        # Configuration for advanced features
        self.registration_config = {
            'max_concurrent_registrations': 5,  # Limit concurrent registrations
            'registration_delay_base': 0.5,     # Base delay between registrations (seconds)
            'registration_delay_jitter': 0.2,   # Random jitter to add
            'enable_throttling': True
        }
        
        self.poisson_config = {
            'enable_poisson_distribution': True,
            'lambda_rate': 1.0,              # Rate parameter for Poisson (events per minute)
            'min_interval': 0.1,             # Minimum interval between messages (seconds)
            'max_interval': 300.0,           # Maximum interval between messages (seconds)
            'distribution_window': 100       # Window size for calculating distribution stats
        }
        
        self.protocol_stats = {}
        self.test_start_time = None
        self.test_end_time = None
        self.running = False
        
        # Registration throttling
        self._registration_semaphore = threading.Semaphore(
            self.registration_config['max_concurrent_registrations']
        )
        self._registration_lock = threading.Lock()
        
        # SLA thresholds
        self.sla_thresholds = {
            'p95_latency_ms': 200,
            'p99_latency_ms': 500,
            'success_rate_percent': 99.5,
            'min_throughput_rps': 10
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

    def generate_report(self, tenants: List[str], devices: List[Device], report_dir: str): # report_dir is now the main output folder path
        """Generate detailed test report with charts directly into the specified report_dir."""
        # import os # Not strictly needed if only using Path
        # import datetime # Already imported at module level

        report_path = Path(report_dir) # This is the main timestamped run folder
        # The report_path directory is already created by stress.py's main()

        # Generate timestamp for unique report filename (within the run folder)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        # Use a more generic name or keep the timestamp if multiple reports per run are possible (not typical here)
        report_file_name = f"hono_test_report_{timestamp}.txt"
        report_file = report_path / report_file_name
        
        test_duration = 0.0
        if self.test_start_time:
            end_time = self.test_end_time or time.time()
            test_duration = end_time - self.test_start_time
        
        report_content = self._generate_report_content(tenants, devices, test_duration)
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f: # Ensure UTF-8 for report file
                f.write(report_content)
            self.logger.info(f"Report saved to: {report_file.resolve()}")
        except Exception as e:
            self.logger.error(f"Failed to save report: {e}")
            return str(report_path) # Return base path even on error

        if REPORTING_AVAILABLE:
            graph_references = []
            original_backend = None
            backend_switched = False
            try:
                current_backend = plt.get_backend()
                if current_backend.lower() != 'agg':
                    original_backend = current_backend
                    plt.switch_backend('Agg')
                    backend_switched = True
            except Exception as e:
                self.logger.warning(f"Could not switch matplotlib backend to Agg: {e}. Graphs might not save correctly.")

            plot_functions = [
                self._plot_throughput_over_time,
                self._plot_latency_over_time,
                self._plot_latency_distribution
            ]
            if self.advanced_metrics.registration_delays: # Check if data exists
                plot_functions.append(self._plot_registration_delays)
            if self.advanced_metrics.poisson_intervals: # Check if data exists
                plot_functions.append(self._plot_poisson_intervals)

            for plot_func in plot_functions:
                try:
                    # Pass report_path (the main run folder) to plotting functions
                    graph_file_path_obj = plot_func(report_path, timestamp) # plot_func returns Path object or None
                    if graph_file_path_obj:
                        # Graph files are in the same directory as the report, so just use the name.
                        graph_references.append(f"{plot_func.__name__.replace('_plot_', '').replace('_', ' ').title()}: {graph_file_path_obj.name}")
                except Exception as e_plot:
                    self.logger.error(f"Error generating graph with {plot_func.__name__}: {e_plot}", exc_info=True)
            
            if graph_references:
                # Append graph references to the existing report content string
                # This part needs to be careful not to add to a file that's already closed or partially written.
                # It's better to build the full report_content string first, then write once.
                # Let's assume _generate_report_content returns the base, and we append here.
                
                graph_section = "\n\nGENERATED GRAPHS\n----------------------------------------\n"
                graph_section += "\n".join(graph_references)
                # Graphs are saved in report_path, which is the main run folder.
                graph_section += f"\nGraphs saved in: {report_path.resolve()}"
                
                report_content += graph_section # Append to the string

                try:
                    with open(report_file, 'w', encoding='utf-8') as f: # Overwrite with full content including graphs
                        f.write(report_content)
                    self.logger.info(f"Report updated with graph references: {report_file.resolve()}")
                except Exception as e:
                    self.logger.error(f"Failed to update report with graph references: {e}")

            if backend_switched and original_backend:
                try:
                    plt.switch_backend(original_backend)
                except Exception as e:
                    self.logger.warning(f"Could not switch matplotlib backend back to {original_backend}: {e}")
        else:
            self.logger.info("Matplotlib/Pandas not available. Skipping graph generation.")
        
        return str(report_file.resolve()) # Return the full path to the generated report file

    def update_validation_stats(self, success_count: int, failure_count: int, total_devices: int):
        """Updates the validation statistics."""
        self.performance_metrics['validation_success'] = success_count
        self.performance_metrics['validation_failed'] = failure_count
        self.performance_metrics['total_validated_devices'] = total_devices
        self.logger.debug(f"ReportingManager validation stats updated: Success={success_count}, Failed={failure_count}, Total={total_devices}")

    def _generate_report_content(self, tenants: List[str], devices: List[Device], test_duration: float) -> str:
        """Generate the content for the test report."""
        import datetime
        
        total_messages = self.stats['messages_sent'] + self.stats['messages_failed']
        success_rate = (self.stats['messages_sent'] / total_messages * 100) if total_messages > 0 else 0
        avg_rate = self.stats['messages_sent'] / test_duration if test_duration > 0 else 0
        
        devices_per_tenant = len(devices) / len(tenants) if tenants else 0
        validation_rate = (self.stats['validation_success'] / (self.stats['validation_success'] + self.stats['validation_failed']) * 100) if (self.stats['validation_success'] + self.stats['validation_failed']) > 0 else 0
        
        # Validate protocol device counts against actual device list
        total_protocol_devices = sum(stats['devices'] for stats in self.protocol_stats.values())
        actual_device_count = len(devices)
        
        if total_protocol_devices != actual_device_count:
            self.logger.warning(f"Device count mismatch: Protocol stats show {total_protocol_devices} devices, but actual count is {actual_device_count}")
            # Fix the device counts
            for protocol_name, stats in self.protocol_stats.items():
                if stats['devices'] > actual_device_count:
                    self.logger.warning(f"Correcting {protocol_name} device count from {stats['devices']} to {actual_device_count}")
                    stats['devices'] = actual_device_count

        report_content = f"""============================================================
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
Devices: {len(devices)} (Actual)
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

        # Add protocol-specific stats with corrected device counts
        for protocol, stats in self.protocol_stats.items():
            protocol_total = stats['messages_sent'] + stats['messages_failed']
            protocol_success_rate = (stats['messages_sent'] / protocol_total * 100) if protocol_total > 0 else 100.0
            
            report_content += f"""
Protocol: {protocol.upper()}
  Devices: {stats['devices']}
  Messages Sent: {stats['messages_sent']}
  Messages Failed: {stats['messages_failed']}
  Success Rate: {protocol_success_rate:.1f}%"""

        report_content += f"""

============================================================
Report generated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

        return report_content

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
            # Debug logging to track if device count is being modified unexpectedly
            self.logger.debug(f"Message sent for {protocol}. Current device count: {self.protocol_stats[protocol]['devices']}")

    def record_message_failed(self, protocol: str):
        """Record a failed message send."""
        self.stats['messages_failed'] += 1
        if protocol in self.protocol_stats:
            self.protocol_stats[protocol]['messages_failed'] += 1
            # Debug logging to track if device count is being modified unexpectedly
            self.logger.debug(f"Message failed for {protocol}. Current device count: {self.protocol_stats[protocol]['devices']}")

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

    def record_registration_attempt(self, device_id: str, delay_applied: float, success: bool):
        """Record device registration attempt with throttling metrics."""
        with self._registration_lock:
            self.stats['registration_attempts'] += 1
            if delay_applied > 0:
                self.stats['registration_throttled'] += 1
                self.advanced_metrics.registration_delays.append(delay_applied)
            
            if success:
                self.stats['devices_registered'] += 1
                self.logger.debug(f"Registration successful for {device_id} (delay: {delay_applied:.2f}s)")
            else:
                self.logger.warning(f"Registration failed for {device_id} after {delay_applied:.2f}s delay")

    def calculate_registration_delay(self, device_index: int, total_devices: int) -> float:
        """Calculate throttled registration delay to prevent adapter overload."""
        if not self.registration_config['enable_throttling']:
            return 0.0
        
        base_delay = self.registration_config['registration_delay_base']
        jitter = random.uniform(0, self.registration_config['registration_delay_jitter'])
        
        # Progressive delay: later devices get slightly longer delays
        progressive_factor = (device_index / total_devices) * 0.5
        
        total_delay = base_delay + jitter + progressive_factor
        
        self.logger.debug(f"Registration delay for device {device_index}/{total_devices}: {total_delay:.2f}s")
        return total_delay

    def generate_poisson_interval(self, base_interval: float) -> float:
        """Generate message interval using Poisson distribution."""
        if not self.poisson_config['enable_poisson_distribution']:
            return base_interval
        
        # Convert base interval to lambda (rate per minute)
        lambda_rate = 60.0 / base_interval if base_interval > 0 else self.poisson_config['lambda_rate']
        
        # Generate interval using exponential distribution (time between Poisson events)
        try:
            # Exponential distribution for time between events
            interval = np.random.exponential(1.0 / (lambda_rate / 60.0))
            
            # Apply bounds
            interval = max(self.poisson_config['min_interval'], 
                          min(self.poisson_config['max_interval'], interval))
            
            # Record for statistics
            self.advanced_metrics.poisson_intervals.append(interval)
            
            # Keep only recent intervals for rolling statistics
            if len(self.advanced_metrics.poisson_intervals) > self.poisson_config['distribution_window']:
                self.advanced_metrics.poisson_intervals.pop(0)
            
            self.logger.debug(f"Poisson interval: {interval:.2f}s (base: {base_interval:.2f}s, λ: {lambda_rate:.2f}/min)")
            return interval
            
        except Exception as e:
            self.logger.warning(f"Error generating Poisson interval: {e}, using base interval")
            return base_interval

    def update_distribution_statistics(self):
        """Update statistics about message distribution patterns."""
        if not self.advanced_metrics.poisson_intervals:
            return
        
        intervals = self.advanced_metrics.poisson_intervals
        
        # Calculate distribution statistics
        mean_interval = np.mean(intervals)
        variance = np.var(intervals)
        std_dev = np.std(intervals)
        
        # Coefficient of variation (relative variability)
        cv = std_dev / mean_interval if mean_interval > 0 else 0
        
        # Calculate actual lambda rate
        actual_lambda = 60.0 / mean_interval if mean_interval > 0 else 0
        
        self.advanced_metrics.message_distribution_stats.update({
            'mean_interval': mean_interval,
            'variance': variance,
            'coefficient_of_variation': cv,
            'actual_lambda': actual_lambda,
            'std_deviation': std_dev,
            'sample_size': len(intervals)
        })

    def record_adapter_load(self, current_connections: int, current_message_rate: float):
        """Record current adapter load metrics."""
        load_metric = current_connections + (current_message_rate * 0.1)  # Weighted load metric
        
        self.advanced_metrics.adapter_load_metrics['current_load'] = load_metric
        self.advanced_metrics.adapter_load_metrics['load_samples'].append(load_metric)
        
        # Update peak load
        if load_metric > self.advanced_metrics.adapter_load_metrics['peak_load']:
            self.advanced_metrics.adapter_load_metrics['peak_load'] = load_metric
        
        # Update average (rolling window)
        if len(self.advanced_metrics.adapter_load_metrics['load_samples']) > 100:
            self.advanced_metrics.adapter_load_metrics['load_samples'].pop(0)
        
        samples = self.advanced_metrics.adapter_load_metrics['load_samples']
        self.advanced_metrics.adapter_load_metrics['avg_load'] = sum(samples) / len(samples)

    def generate_advanced_report_content(self, tenants: List[str], devices: List[Device], test_duration: float) -> str:
        """Generate enhanced report with advanced metrics."""
        base_content = self._generate_report_content(tenants, devices, test_duration)
        
        # Calculate advanced statistics
        self.update_distribution_statistics()
        
        advanced_section = f"""

ADVANCED LOAD TESTING METRICS
========================================

REGISTRATION THROTTLING
----------------------------------------
Total Registration Attempts: {self.stats['registration_attempts']}
Successful Registrations: {self.stats['devices_registered']}
Throttled Registrations: {self.stats['registration_throttled']}
Registration Success Rate: {(self.stats['devices_registered'] / max(self.stats['registration_attempts'], 1) * 100):.1f}%
Average Registration Delay: {np.mean(self.advanced_metrics.registration_delays) if self.advanced_metrics.registration_delays else 0:.2f}s
Max Registration Delay: {max(self.advanced_metrics.registration_delays) if self.advanced_metrics.registration_delays else 0:.2f}s

POISSON MESSAGE DISTRIBUTION
----------------------------------------
Poisson Distribution: {'Enabled' if self.poisson_config['enable_poisson_distribution'] else 'Disabled'}
Total Intervals Generated: {len(self.advanced_metrics.poisson_intervals)}
Mean Interval: {self.advanced_metrics.message_distribution_stats.get('mean_interval', 0):.2f}s
Interval Variance: {self.advanced_metrics.message_distribution_stats.get('variance', 0):.2f}
Coefficient of Variation: {self.advanced_metrics.message_distribution_stats.get('coefficient_of_variation', 0):.3f}
Actual Lambda Rate: {self.advanced_metrics.message_distribution_stats.get('actual_lambda', 0):.2f} events/minute
Expected vs Actual Rate Deviation: {abs(self.poisson_config['lambda_rate'] - self.advanced_metrics.message_distribution_stats.get('actual_lambda', 0)):.2f} events/minute

ADAPTER LOAD METRICS
----------------------------------------
Current Load: {self.advanced_metrics.adapter_load_metrics['current_load']:.2f}
Peak Load: {self.advanced_metrics.adapter_load_metrics['peak_load']:.2f}
Average Load: {self.advanced_metrics.adapter_load_metrics['avg_load']:.2f}
Load Samples Collected: {len(self.advanced_metrics.adapter_load_metrics['load_samples'])}

DISTRIBUTION ANALYSIS
----------------------------------------"""

        if self.advanced_metrics.poisson_intervals:
            intervals = self.advanced_metrics.poisson_intervals
            
            # Calculate percentiles for intervals
            percentiles = self.calculate_percentiles(intervals, [25, 50, 75, 90, 95, 99])
            
            advanced_section += f"""
Interval Percentiles:
  P25: {percentiles.get('p25', 0):.2f}s
  P50 (Median): {percentiles.get('p50', 0):.2f}s
  P75: {percentiles.get('p75', 0):.2f}s
  P90: {percentiles.get('p90', 0):.2f}s
  P95: {percentiles.get('p95', 0):.2f}s
  P99: {percentiles.get('p99', 0):.2f}s

Min Interval: {min(intervals):.2f}s
Max Interval: {max(intervals):.2f}s"""

        return base_content + advanced_section

    def print_advanced_findings(self):
        """Print advanced analysis findings."""
        print("\n" + "="*80)
        print("🔬 ADVANCED LOAD TESTING ANALYSIS")
        print("="*80)
        
        # Registration Analysis
        if self.stats['registration_attempts'] > 0:
            reg_success_rate = (self.stats['devices_registered'] / self.stats['registration_attempts']) * 100
            throttling_rate = (self.stats['registration_throttled'] / self.stats['registration_attempts']) * 100
            
            print(f"📋 Registration Analysis:")
            print(f"   Success Rate: {reg_success_rate:.1f}%")
            print(f"   Throttling Applied: {throttling_rate:.1f}% of registrations")
            
            if self.advanced_metrics.registration_delays:
                avg_delay = np.mean(self.advanced_metrics.registration_delays)
                print(f"   Average Throttling Delay: {avg_delay:.2f}s")
        
        # Distribution Analysis
        if self.advanced_metrics.poisson_intervals:
            self.update_distribution_statistics()
            stats = self.advanced_metrics.message_distribution_stats
            
            print(f"\n📊 Message Distribution Analysis:")
            print(f"   Distribution Type: {'Poisson' if self.poisson_config['enable_poisson_distribution'] else 'Fixed'}")
            print(f"   Mean Interval: {stats.get('mean_interval', 0):.2f}s")
            print(f"   Coefficient of Variation: {stats.get('coefficient_of_variation', 0):.3f}")
            print(f"   Actual Rate: {stats.get('actual_lambda', 0):.2f} events/min")
            
            # Distribution quality assessment
            cv = stats.get('coefficient_of_variation', 0)
            if cv < 0.5:
                quality = "🟢 Low variability (consistent)"
            elif cv < 1.0:
                quality = "🟡 Moderate variability"
            else:
                quality = "🔴 High variability (bursty)"
            print(f"   Distribution Quality: {quality}")
        
        # Adapter Load Analysis
        load_metrics = self.advanced_metrics.adapter_load_metrics
        if load_metrics['load_samples']:
            print(f"\n⚙️  Adapter Load Analysis:")
            print(f"   Peak Load: {load_metrics['peak_load']:.2f}")
            print(f"   Average Load: {load_metrics['avg_load']:.2f}")
            print(f"   Current Load: {load_metrics['current_load']:.2f}")
            
            # Load stability assessment
            if load_metrics['peak_load'] > load_metrics['avg_load'] * 2:
                stability = "🔴 Unstable (high peaks)"
            elif load_metrics['peak_load'] > load_metrics['avg_load'] * 1.5:
                stability = "🟡 Moderate stability"
            else:
                stability = "🟢 Stable load"
            print(f"   Load Stability: {stability}")
        
        print("="*80)

    # --- Plotting Methods ---
    def _plot_throughput_over_time(self, output_dir: Path, timestamp: str) -> Optional[Path]: # output_dir is the main run folder
        if not REPORTING_AVAILABLE: return None
        if not self.time_series_data.get('timestamps') or not self.time_series_data.get('msg_rate'):
            self.logger.warning("No throughput data to plot (timestamps or msg_rate missing).")
            return None
        
        fig_name = f"throughput_over_time_{timestamp}.png"
        fig_path = output_dir / fig_name
        try:
            plt.figure(figsize=(12, 6))
            plt.plot(self.time_series_data['timestamps'], self.time_series_data['msg_rate'], label='Message Rate (msg/sec)', color='blue', linewidth=2)
            
            # Optional: Plot cumulative messages sent
            # if self.time_series_data.get('messages_sent'):
            #     ax2 = plt.gca().twinx()
            #     ax2.plot(self.time_series_data['timestamps'], self.time_series_data['messages_sent'], label='Total Sent', color='green', linestyle='--', alpha=0.7)
            #     ax2.set_ylabel("Total Messages Sent")
            #     ax2.legend(loc='upper right')

            plt.xlabel("Time")
            plt.ylabel("Rate (msg/sec)")
            plt.title("Throughput Over Time")
            plt.gca().legend(loc='upper left')
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(fig_path)
            plt.close()
            self.logger.info(f"Throughput graph saved to {fig_path}")
            return fig_path
        except Exception as e:
            self.logger.error(f"Failed to plot throughput graph: {e}", exc_info=True)
            if plt.gcf().get_axes(): plt.close()
            return None

    def _plot_latency_over_time(self, output_dir: Path, timestamp: str) -> Optional[Path]: # output_dir is the main run folder
        if not REPORTING_AVAILABLE: return None
        if not self.time_series_data.get('timestamps'):
            self.logger.warning("No timestamps for latency over time plot.")
            return None

        fig_name = f"latency_over_time_{timestamp}.png"
        fig_path = output_dir / fig_name
        plotted_anything = False
        try:
            plt.figure(figsize=(12, 6))
            if self.time_series_data.get('avg_latency') and any(self.time_series_data['avg_latency']):
                plt.plot(self.time_series_data['timestamps'], self.time_series_data['avg_latency'], label='Avg Latency (ms)', color='green', linewidth=1.5)
                plotted_anything = True
            if self.time_series_data.get('latency_95th') and any(self.time_series_data['latency_95th']):
                plt.plot(self.time_series_data['timestamps'], self.time_series_data['latency_95th'], label='P95 Latency (ms)', color='orange', linewidth=1.5)
                plotted_anything = True
            if self.time_series_data.get('latency_99th') and any(self.time_series_data['latency_99th']):
                plt.plot(self.time_series_data['timestamps'], self.time_series_data['latency_99th'], label='P99 Latency (ms)', color='red', linewidth=1.5)
                plotted_anything = True
            
            if not plotted_anything:
                self.logger.warning("No valid latency series to plot for latency over time.")
                plt.close()
                return None

            plt.xlabel("Time")
            plt.ylabel("Latency (ms)")
            plt.title("Latency Over Time")
            plt.legend()
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(fig_path)
            plt.close()
            self.logger.info(f"Latency over time graph saved to {fig_path}")
            return fig_path
        except Exception as e:
            self.logger.error(f"Failed to plot latency over time graph: {e}", exc_info=True)
            if plt.gcf().get_axes(): plt.close()
            return None

    def _plot_latency_distribution(self, output_dir: Path, timestamp: str) -> Optional[Path]: # output_dir is the main run folder
        if not REPORTING_AVAILABLE: return None
        if not self.performance_metrics.get('response_times') or not self.performance_metrics['response_times']:
            self.logger.warning("No response time data for latency distribution plot.")
            return None
        
        fig_name = f"latency_distribution_{timestamp}.png"
        fig_path = output_dir / fig_name
        try:
            plt.figure(figsize=(10, 6))
            # Filter out potential None or non-numeric values if any
            valid_response_times = [rt for rt in self.performance_metrics['response_times'] if isinstance(rt, (int, float))]
            if not valid_response_times:
                self.logger.warning("No valid numeric response time data for latency distribution plot.")
                plt.close()
                return None

            plt.hist(valid_response_times, bins=50, color='skyblue', edgecolor='black', alpha=0.75)
            plt.xlabel("Latency (ms)")
            plt.ylabel("Frequency")
            plt.title("Latency Distribution")
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            plt.tight_layout()
            plt.savefig(fig_path)
            plt.close()
            self.logger.info(f"Latency distribution graph saved to {fig_path}")
            return fig_path
        except Exception as e:
            self.logger.error(f"Failed to plot latency distribution graph: {e}", exc_info=True)
            if plt.gcf().get_axes(): plt.close()
            return None

    def _plot_registration_delays(self, output_dir: Path, timestamp: str) -> Optional[Path]: # output_dir is the main run folder
        if not REPORTING_AVAILABLE: return None
        if not self.advanced_metrics.registration_delays:
            self.logger.info("No registration delay data to plot (feature might be disabled or no delays recorded).")
            return None
        
        fig_name = f"registration_delays_{timestamp}.png"
        fig_path = output_dir / fig_name
        try:
            plt.figure(figsize=(10, 6))
            plt.hist(self.advanced_metrics.registration_delays, bins=30, color='lightcoral', edgecolor='black', alpha=0.75)
            plt.xlabel("Delay (s)")
            plt.ylabel("Frequency")
            plt.title("Registration Delay Distribution (Throttling)")
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            plt.tight_layout()
            plt.savefig(fig_path)
            plt.close()
            self.logger.info(f"Registration delay graph saved to {fig_path}")
            return fig_path
        except Exception as e:
            self.logger.error(f"Failed to plot registration delay graph: {e}", exc_info=True)
            if plt.gcf().get_axes(): plt.close()
            return None

    def _plot_poisson_intervals(self, output_dir: Path, timestamp: str) -> Optional[Path]: 
        if not REPORTING_AVAILABLE: return None
        if not self.advanced_metrics.poisson_intervals:
            self.logger.info("No Poisson interval data to plot (feature might be disabled or no intervals recorded).")
            return None
        
        fig_name = f"poisson_intervals_{timestamp}.png"
        fig_path = output_dir / fig_name
        try:
            plt.figure(figsize=(10, 6))
            plt.hist(self.advanced_metrics.poisson_intervals, bins=30, color='mediumseagreen', edgecolor='black', alpha=0.75)
            plt.xlabel("Interval (s)")
            plt.ylabel("Frequency")
            plt.title("Poisson Message Interval Distribution")
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            plt.tight_layout()
            plt.savefig(fig_path)
            plt.close()
            self.logger.info(f"Poisson interval graph saved to {fig_path}")
            return fig_path # Return Path object for consistency
        except Exception as e:
            self.logger.error(f"Failed to plot Poisson interval graph: {e}", exc_info=True)
            if plt.gcf().get_axes(): plt.close()
            return None
