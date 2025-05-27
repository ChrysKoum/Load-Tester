"""
Reporting module for Hono Load Test Suite.
Handles statistics collection, monitoring, and report generation.
"""

import time
import datetime
import threading
import logging
from pathlib import Path
from typing import Dict, List

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
            'msg_rate': []
        }
        
        self.protocol_stats = {}  # Track stats per protocol
        self.test_start_time = None
        self.test_end_time = None
        self.running = False
    
    def initialize_test(self, protocols: List[str]):
        """Initialize test start time and protocol stats."""
        self.test_start_time = datetime.datetime.now()
        for protocol in protocols:
            self.protocol_stats[protocol.lower()] = {
                'messages_sent': 0,
                'messages_failed': 0,
                'devices': 0
            }
    
    def set_running(self, running: bool):
        """Set the running state for monitoring."""
        self.running = running
    
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
    
    def generate_report(self, tenants: List[str], devices: List, report_dir: str = "./reports"):
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
            f.write(f"Tenants: {len(tenants)}\n")
            f.write(f"Devices: {len(devices)}\n")
            f.write(f"Devices per Tenant: {len(devices) / max(1, len(tenants)):.1f}\n\n")
            
            f.write("VALIDATION RESULTS\n")
            f.write("-" * 40 + "\n")
            f.write(f"Validation Success: {self.stats['validation_success']}\n")
            f.write(f"Validation Failed: {self.stats['validation_failed']}\n")
            f.write(f"Validation Rate: {self.stats['validation_success'] / max(1, len(devices)) * 100:.1f}%\n\n")
            
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
