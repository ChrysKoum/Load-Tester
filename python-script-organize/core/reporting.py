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

    def record_latency_metrics(self, response_time_ms: float):
        """Record latency metrics and check SLA violations."""
        self.performance_metrics['response_times'].append(response_time_ms)
        self.performance_metrics['latency_history'].append(response_time_ms)
        
        # Keep only last 1000 measurements for sliding window
        if len(self.performance_metrics['latency_history']) > 1000:
            self.performance_metrics['latency_history'].pop(0)
        
        # Track SLA violations
        if response_time_ms > 1000:
            self.performance_metrics['latency_sla_violations']['1000ms'] += 1
        elif response_time_ms > 500:
            self.performance_metrics['latency_sla_violations']['500ms'] += 1
        elif response_time_ms > 200:
            self.performance_metrics['latency_sla_violations']['200ms'] += 1
        elif response_time_ms > 100:
            self.performance_metrics['latency_sla_violations']['100ms'] += 1
        elif response_time_ms > 50:
            self.performance_metrics['latency_sla_violations']['50ms'] += 1

    def calculate_percentiles(self, data_list):
        """Calculate various percentiles from a data list."""
        if not data_list:
            return {}
        
        sorted_data = sorted(data_list)
        length = len(sorted_data)
        
        percentiles = {}
        for p in [50, 90, 95, 99, 99.9]:
            index = int((p / 100.0) * length)
            if index >= length:
                index = length - 1
            percentiles[f'p{p}'] = sorted_data[index]
        
        return percentiles

    def get_real_time_latency_stats(self):
        """Get real-time latency statistics."""
        if not self.performance_metrics['latency_history']:
            return None
        
        recent_latencies = self.performance_metrics['latency_history'][-100:]  # Last 100 measurements
        percentiles = self.calculate_percentiles(recent_latencies)
        
        return {
            'current_avg': sum(recent_latencies) / len(recent_latencies),
            'current_min': min(recent_latencies),
            'current_max': max(recent_latencies),
            'percentiles': percentiles,
            'sample_size': len(recent_latencies)
        }

    def check_performance_degradation(self):
        """Check for performance degradation over time."""
        if len(self.performance_metrics['response_times']) < 100:
            return None
        
        # Compare first quarter vs last quarter of test
        total_measurements = len(self.performance_metrics['response_times'])
        quarter_size = total_measurements // 4
        
        if quarter_size < 10:
            return None
        
        baseline = self.performance_metrics['response_times'][:quarter_size]
        current = self.performance_metrics['response_times'][-quarter_size:]
        
        baseline_avg = sum(baseline) / len(baseline)
        current_avg = sum(current) / len(current)
        
        degradation = ((current_avg - baseline_avg) / baseline_avg) * 100 if baseline_avg > 0 else 0
        
        self.performance_metrics['performance_degradation'] = {
            'baseline_latency': baseline_avg,
            'current_latency': current_avg,
            'degradation_percentage': degradation
        }
        
        return degradation

    def analyze_latency_patterns(self):
        """Analyze latency patterns and anomalies."""
        if len(self.performance_metrics['response_times']) < 50:
            return {}
        
        latencies = self.performance_metrics['response_times']
        percentiles = self.calculate_percentiles(latencies)
        
        # Calculate standard deviation
        mean_latency = sum(latencies) / len(latencies)
        variance = sum((x - mean_latency) ** 2 for x in latencies) / len(latencies)
        std_dev = variance ** 0.5
        
        # Identify outliers (values beyond 2 standard deviations)
        outliers = [x for x in latencies if abs(x - mean_latency) > 2 * std_dev]
        
        # Calculate jitter (variability)
        jitter = std_dev / mean_latency * 100 if mean_latency > 0 else 0
        
        return {
            'percentiles': percentiles,
            'mean': mean_latency,
            'std_dev': std_dev,
            'jitter_percent': jitter,
            'outliers_count': len(outliers),
            'outliers_percent': (len(outliers) / len(latencies)) * 100,
            'consistency_score': max(0, 100 - jitter)  # Higher is more consistent
        }

    def print_advanced_findings(self):
        """Print advanced performance findings and analysis."""
        print("\n" + "="*80)
        print("🔬 ADVANCED PERFORMANCE ANALYSIS")
        print("="*80)
        
        # Latency Analysis
        latency_analysis = self.analyze_latency_patterns()
        if latency_analysis:
            print(f"\n📊 Latency Analysis:")
            percentiles = latency_analysis['percentiles']
            
            print(f"   Mean latency: {latency_analysis['mean']:.1f} ms")
            print(f"   Standard deviation: {latency_analysis['std_dev']:.1f} ms")
            print(f"   Jitter: {latency_analysis['jitter_percent']:.1f}%")
            print(f"   Consistency Score: {latency_analysis['consistency_score']:.1f}/100")
            
            print(f"\n📈 Latency Percentiles:")
            for key, value in percentiles.items():
                print(f"   {key}: {value:.1f} ms")
            
            # SLA Compliance Check
            print(f"\n🎯 SLA Compliance:")
            p95_compliant = percentiles.get('p95', 0) <= self.sla_thresholds['p95_latency_ms']
            p99_compliant = percentiles.get('p99', 0) <= self.sla_thresholds['p99_latency_ms']
            
            p95_status = "✅ PASS" if p95_compliant else "❌ FAIL"
            p99_status = "✅ PASS" if p99_compliant else "❌ FAIL"
            
            print(f"   95th percentile < {self.sla_thresholds['p95_latency_ms']}ms: {p95_status} ({percentiles.get('p95', 0):.1f}ms)")
            print(f"   99th percentile < {self.sla_thresholds['p99_latency_ms']}ms: {p99_status} ({percentiles.get('p99', 0):.1f}ms)")
            
            # Outlier Analysis
            if latency_analysis['outliers_count'] > 0:
                print(f"\n⚠️  Outlier Detection:")
                print(f"   Outliers found: {latency_analysis['outliers_count']} ({latency_analysis['outliers_percent']:.1f}%)")
                if latency_analysis['outliers_percent'] > 5:
                    print(f"   🚨 High outlier rate detected - investigate network/server issues")
                elif latency_analysis['outliers_percent'] > 1:
                    print(f"   ⚠️  Moderate outlier rate - monitor for patterns")
                else:
                    print(f"   ✅ Low outlier rate - acceptable variance")
        
        # Performance Degradation Analysis
        degradation = self.check_performance_degradation()
        if degradation is not None:
            print(f"\n📉 Performance Degradation Analysis:")
            baseline = self.performance_metrics['performance_degradation']['baseline_latency']
            current = self.performance_metrics['performance_degradation']['current_latency']
            
            print(f"   Baseline latency: {baseline:.1f} ms")
            print(f"   Current latency: {current:.1f} ms")
            print(f"   Change: {degradation:+.1f}%")
            
            if degradation > 20:
                print(f"   🚨 Significant performance degradation detected!")
                print(f"   💡 Investigate: memory leaks, resource exhaustion, network issues")
            elif degradation > 10:
                print(f"   ⚠️  Moderate performance degradation")
                print(f"   💡 Monitor: check for gradual resource consumption")
            elif degradation < -10:
                print(f"   🚀 Performance improvement detected")
                print(f"   💡 System may have warmed up or optimized")
            else:
                print(f"   ✅ Stable performance throughout test")
        
        # Connection Analysis
        conn_metrics = self.performance_metrics['connection_metrics']
        if conn_metrics['total_connections'] > 0:
            print(f"\n🔗 Connection Analysis:")
            conn_success_rate = ((conn_metrics['total_connections'] - conn_metrics['failed_connections']) / 
                               conn_metrics['total_connections'] * 100)
            print(f"   Connection success rate: {conn_success_rate:.1f}%")
            print(f"   Failed connections: {conn_metrics['failed_connections']}")
            print(f"   Reconnections: {conn_metrics['reconnections']}")
            
            if conn_metrics['connection_times']:
                avg_conn_time = sum(conn_metrics['connection_times']) / len(conn_metrics['connection_times'])
                print(f"   Average connection time: {avg_conn_time:.1f} ms")
        
        # SLA Violations Summary
        violations = self.performance_metrics['latency_sla_violations']
        total_requests = sum(violations.values()) if violations else 0
        
        if total_requests > 0:
            print(f"\n🚨 SLA Violation Summary:")
            print(f"   Total requests with violations: {total_requests}")
            for threshold, count in violations.items():
                if count > 0:
                    percentage = (count / total_requests) * 100
                    print(f"   > {threshold}: {count} requests ({percentage:.1f}%)")
        
        # Performance Recommendations
        print(f"\n💡 Performance Recommendations:")
        
        if latency_analysis:
            if latency_analysis['jitter_percent'] > 30:
                print(f"   🔧 High latency jitter detected - check network stability")
            
            if latency_analysis['percentiles'].get('p99', 0) > 1000:
                print(f"   🔧 Very high tail latencies - investigate slow queries/operations")
            
            if latency_analysis['consistency_score'] < 70:
                print(f"   🔧 Poor latency consistency - consider load balancing improvements")
        
        if degradation and degradation > 15:
            print(f"   🔧 Performance degradation detected - investigate resource leaks")
        
        conn_success_rate = 100
        if conn_metrics['total_connections'] > 0:
            conn_success_rate = ((conn_metrics['total_connections'] - conn_metrics['failed_connections']) / 
                               conn_metrics['total_connections'] * 100)
        
        if conn_success_rate < 99:
            print(f"   🔧 Connection reliability issues - check network/server capacity")
        
        # Overall System Health Score
        health_factors = []
        
        if latency_analysis:
            # Latency health (0-100)
            p95_health = max(0, 100 - (latency_analysis['percentiles'].get('p95', 0) / 5))  # 500ms = 0 health
            health_factors.append(('Latency', min(100, p95_health)))
            
            # Consistency health
            health_factors.append(('Consistency', latency_analysis['consistency_score']))
        
        # Success rate health
        total_messages = self.stats['messages_sent'] + self.stats['messages_failed']
        if total_messages > 0:
            success_rate = (self.stats['messages_sent'] / total_messages) * 100
            health_factors.append(('Success Rate', success_rate))
        
        # Connection health
        health_factors.append(('Connection Health', conn_success_rate))
        
        if health_factors:
            overall_health = sum(factor[1] for factor in health_factors) / len(health_factors)
            print(f"\n📊 System Health Score: {overall_health:.1f}/100")
            
            for factor_name, score in health_factors:
                status = "🟢" if score >= 90 else "🟡" if score >= 70 else "🔴"
                print(f"   {status} {factor_name}: {score:.1f}/100")
            
            if overall_health >= 90:
                print(f"   ✅ Excellent system health")
            elif overall_health >= 80:
                print(f"   ✅ Good system health")
            elif overall_health >= 70:
                print(f"   ⚠️  Fair system health - room for improvement")
            else:
                print(f"   🚨 Poor system health - requires attention")
        
        print("="*80)

    # Update the existing record_message_metrics method
    def record_message_metrics(self, protocol: str, response_time_ms: float, 
                              response_code: int, message_size_bytes: int):
        """Record detailed metrics for each message sent."""
        # Record response time and latency metrics
        self.performance_metrics['response_times'].append(response_time_ms)
        self.record_latency_metrics(response_time_ms)
        
        # Record response code
        if response_code not in self.performance_metrics['response_codes']:
            self.performance_metrics['response_codes'][response_code] = 0
        self.performance_metrics['response_codes'][response_code] += 1
        
        # Record data transfer
        self.performance_metrics['data_transferred']['total_bytes'] += message_size_bytes
        self.performance_metrics['data_transferred']['request_bytes'] += message_size_bytes
        self.performance_metrics['data_transferred']['min_message_size'] = min(
            self.performance_metrics['data_transferred']['min_message_size'], message_size_bytes)
        self.performance_metrics['data_transferred']['max_message_size'] = max(
            self.performance_metrics['data_transferred']['max_message_size'], message_size_bytes)
        
        # Per-protocol metrics
        if protocol not in self.performance_metrics['protocol_performance']:
            self.performance_metrics['protocol_performance'][protocol] = {
                'response_times': [],
                'response_codes': {},
                'data_transferred': 0,
                'connect_times': [],  # Connection establishment times
                'publish_times': [],  # Time to publish/send
                'ack_times': []       # Acknowledgment times (for MQTT QoS 1/2)
            }
        
        self.performance_metrics['protocol_performance'][protocol]['response_times'].append(response_time_ms)
        
        if response_code not in self.performance_metrics['protocol_performance'][protocol]['response_codes']:
            self.performance_metrics['protocol_performance'][protocol]['response_codes'][response_code] = 0
        self.performance_metrics['protocol_performance'][protocol]['response_codes'][response_code] += 1
        
        self.performance_metrics['protocol_performance'][protocol]['data_transferred'] += message_size_bytes

    def record_connection_metrics(self, success: bool, connection_time_ms: float = 0):
        """Record connection-level metrics."""
        self.performance_metrics['connection_metrics']['total_connections'] += 1
        
        if not success:
            self.performance_metrics['connection_metrics']['failed_connections'] += 1
        else:
            if connection_time_ms > 0:
                self.performance_metrics['connection_metrics']['connection_times'].append(connection_time_ms)

    def record_reconnection(self):
        """Record a reconnection event."""
        self.performance_metrics['connection_metrics']['reconnections'] += 1

    # Update monitor_stats to include real-time latency tracking
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
                
                # Get real-time latency stats
                latency_stats = self.get_real_time_latency_stats()
                
                # Store time series data for reporting
                self.time_series_data['timestamps'].append(datetime.datetime.now())
                self.time_series_data['messages_sent'].append(current_sent)
                self.time_series_data['messages_failed'].append(self.stats['messages_failed'])
                self.time_series_data['msg_rate'].append(rate)
                
                if latency_stats:
                    self.time_series_data['avg_latency'].append(latency_stats['current_avg'])
                    self.time_series_data['latency_95th'].append(latency_stats['percentiles'].get('p95', 0))
                    self.time_series_data['latency_99th'].append(latency_stats['percentiles'].get('p99', 0))
                else:
                    self.time_series_data['avg_latency'].append(0)
                    self.time_series_data['latency_95th'].append(0)
                    self.time_series_data['latency_99th'].append(0)
                
                # Log current stats with latency info
                latency_info = ""
                if latency_stats:
                    latency_info = f", Avg Latency: {latency_stats['current_avg']:.1f}ms, P95: {latency_stats['percentiles'].get('p95', 0):.1f}ms"
                
                self.logger.info(
                    f"Stats - Sent: {current_sent}, Failed: {self.stats['messages_failed']}, "
                    f"Rate: {rate:.1f} msg/s{latency_info}"
                )
                
                # Update for next interval
                last_sent = current_sent
                last_time = current_time
        
        stats_thread = threading.Thread(target=stats_monitor)
        stats_thread.daemon = True
        stats_thread.start()

    # Update the print_final_stats method to include advanced findings
    def print_final_stats(self):
        """Print final statistics (enhanced version)."""
        self.print_enhanced_final_stats()
        self.print_advanced_findings()
