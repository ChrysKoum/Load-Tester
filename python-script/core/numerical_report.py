"""
Numerical Report Generator for Hono Load Test Suite.
Extracts numerical data from graphs and logs for statistical analysis.
"""

import json
import csv
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import datetime
import numpy as np


@dataclass
class NumericalMetrics:
    """Container for numerical metrics extracted from test run."""
    
    # Test metadata
    test_timestamp: str
    test_duration_seconds: float
    test_mode: str
    
    # Infrastructure
    num_tenants: int
    num_devices: int
    protocols: List[str]
    
    # Message statistics
    total_messages_sent: int
    total_messages_failed: int
    success_rate_percent: float
    
    # Throughput metrics
    avg_throughput_msg_per_sec: float
    peak_throughput_msg_per_sec: float
    min_throughput_msg_per_sec: float
    
    # Latency metrics (milliseconds)
    latency_avg_ms: float
    latency_min_ms: float
    latency_max_ms: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_p999_ms: float
    latency_stddev_ms: float
    
    # SLA compliance
    sla_success_rate_target: float
    sla_success_rate_achieved: bool
    sla_p95_latency_target_ms: float
    sla_p95_latency_achieved: bool
    sla_p99_latency_target_ms: float
    sla_p99_latency_achieved: bool
    
    # Resource usage
    peak_memory_mb: float
    avg_memory_mb: float
    peak_cpu_percent: float
    avg_cpu_percent: float
    
    # Error analysis
    total_errors: int
    error_rate_percent: float
    error_types: Dict[str, int]
    
    # Per-protocol breakdown
    protocol_stats: Dict[str, Dict[str, Any]]
    
    # Advanced metrics (if available)
    registration_success_rate: Optional[float] = None
    avg_registration_delay_sec: Optional[float] = None
    poisson_mean_interval_sec: Optional[float] = None
    poisson_coefficient_of_variation: Optional[float] = None
    
    # Time series summary
    throughput_time_series: Optional[List[float]] = None
    latency_time_series: Optional[List[float]] = None
    timestamps: Optional[List[str]] = None


class NumericalReportGenerator:
    """Generates numerical reports from test data for statistical analysis."""
    
    def __init__(self, reporting_manager, test_config: Dict[str, Any]):
        """
        Initialize the numerical report generator.
        
        Args:
            reporting_manager: ReportingManager instance with test data
            test_config: Test configuration dictionary
        """
        self.reporting_manager = reporting_manager
        self.test_config = test_config
        self.logger = logging.getLogger(__name__)
    
    def extract_metrics(self) -> NumericalMetrics:
        """Extract all numerical metrics from the reporting manager."""
        rm = self.reporting_manager
        
        # Calculate test duration
        test_duration = 0.0
        if rm.test_start_time:
            end_time = rm.test_end_time or datetime.datetime.now().timestamp()
            test_duration = end_time - rm.test_start_time
        
        # Calculate throughput metrics
        throughput_data = rm.time_series_data.get('msg_rate', [])
        avg_throughput = np.mean(throughput_data) if throughput_data else 0.0
        peak_throughput = np.max(throughput_data) if throughput_data else 0.0
        min_throughput = np.min(throughput_data) if throughput_data else 0.0
        
        # Calculate latency metrics
        response_times = rm.performance_metrics.get('response_times', [])
        valid_response_times = [rt for rt in response_times if isinstance(rt, (int, float))]
        
        if valid_response_times:
            latency_avg = np.mean(valid_response_times)
            latency_min = np.min(valid_response_times)
            latency_max = np.max(valid_response_times)
            latency_stddev = np.std(valid_response_times)
            latency_p50 = np.percentile(valid_response_times, 50)
            latency_p95 = np.percentile(valid_response_times, 95)
            latency_p99 = np.percentile(valid_response_times, 99)
            latency_p999 = np.percentile(valid_response_times, 99.9)
        else:
            latency_avg = latency_min = latency_max = latency_stddev = 0.0
            latency_p50 = latency_p95 = latency_p99 = latency_p999 = 0.0
        
        # Calculate success rate
        total_messages = rm.stats['messages_sent'] + rm.stats['messages_failed']
        success_rate = (rm.stats['messages_sent'] / total_messages * 100) if total_messages > 0 else 0.0
        error_rate = 100.0 - success_rate
        
        # SLA compliance
        sla_thresholds = rm.sla_thresholds
        sla_success_achieved = success_rate >= sla_thresholds.get('success_rate_percent', 99.5)
        sla_p95_achieved = latency_p95 <= sla_thresholds.get('p95_latency_ms', 200)
        sla_p99_achieved = latency_p99 <= sla_thresholds.get('p99_latency_ms', 500)
        
        # Resource usage
        memory_data = rm.time_series_data.get('memory_usage_mb', [])
        cpu_data = rm.time_series_data.get('cpu_usage_percent', [])
        
        peak_memory = np.max(memory_data) if memory_data else 0.0
        avg_memory = np.mean(memory_data) if memory_data else 0.0
        peak_cpu = np.max(cpu_data) if cpu_data else 0.0
        avg_cpu = np.mean(cpu_data) if cpu_data else 0.0
        
        # Protocol breakdown
        protocol_stats = {}
        for protocol, stats in rm.protocol_stats.items():
            protocol_total = stats['messages_sent'] + stats['messages_failed']
            protocol_success_rate = (stats['messages_sent'] / protocol_total * 100) if protocol_total > 0 else 100.0
            
            protocol_stats[protocol] = {
                'messages_sent': stats['messages_sent'],
                'messages_failed': stats['messages_failed'],
                'success_rate_percent': protocol_success_rate,
                'devices': stats.get('devices', 0)
            }
        
        # Advanced metrics (if available)
        registration_success_rate = None
        avg_registration_delay = None
        if rm.stats.get('registration_attempts', 0) > 0:
            registration_success_rate = (
                rm.stats['devices_registered'] / rm.stats['registration_attempts'] * 100
            )
        
        if hasattr(rm, 'advanced_metrics') and rm.advanced_metrics.registration_delays:
            avg_registration_delay = np.mean(rm.advanced_metrics.registration_delays)
        
        poisson_mean_interval = None
        poisson_cv = None
        if hasattr(rm, 'advanced_metrics') and rm.advanced_metrics.message_distribution_stats:
            poisson_mean_interval = rm.advanced_metrics.message_distribution_stats.get('mean_interval')
            poisson_cv = rm.advanced_metrics.message_distribution_stats.get('coefficient_of_variation')
        
        # Time series data (convert timestamps to strings)
        timestamps = None
        if rm.time_series_data.get('timestamps'):
            timestamps = [ts.isoformat() if hasattr(ts, 'isoformat') else str(ts) 
                         for ts in rm.time_series_data['timestamps']]
        
        return NumericalMetrics(
            test_timestamp=datetime.datetime.now().isoformat(),
            test_duration_seconds=test_duration,
            test_mode=self.test_config.get('test_mode', 'custom'),
            num_tenants=self.test_config.get('num_tenants', 0),
            num_devices=self.test_config.get('num_devices', 0),
            protocols=self.test_config.get('protocols', []),
            total_messages_sent=rm.stats['messages_sent'],
            total_messages_failed=rm.stats['messages_failed'],
            success_rate_percent=success_rate,
            avg_throughput_msg_per_sec=avg_throughput,
            peak_throughput_msg_per_sec=peak_throughput,
            min_throughput_msg_per_sec=min_throughput,
            latency_avg_ms=latency_avg,
            latency_min_ms=latency_min,
            latency_max_ms=latency_max,
            latency_p50_ms=latency_p50,
            latency_p95_ms=latency_p95,
            latency_p99_ms=latency_p99,
            latency_p999_ms=latency_p999,
            latency_stddev_ms=latency_stddev,
            sla_success_rate_target=sla_thresholds.get('success_rate_percent', 99.5),
            sla_success_rate_achieved=sla_success_achieved,
            sla_p95_latency_target_ms=sla_thresholds.get('p95_latency_ms', 200),
            sla_p95_latency_achieved=sla_p95_achieved,
            sla_p99_latency_target_ms=sla_thresholds.get('p99_latency_ms', 500),
            sla_p99_latency_achieved=sla_p99_achieved,
            peak_memory_mb=peak_memory,
            avg_memory_mb=avg_memory,
            peak_cpu_percent=peak_cpu,
            avg_cpu_percent=avg_cpu,
            total_errors=rm.stats['messages_failed'],
            error_rate_percent=error_rate,
            error_types=dict(rm.error_types) if hasattr(rm, 'error_types') else {},
            protocol_stats=protocol_stats,
            registration_success_rate=registration_success_rate,
            avg_registration_delay_sec=avg_registration_delay,
            poisson_mean_interval_sec=poisson_mean_interval,
            poisson_coefficient_of_variation=poisson_cv,
            throughput_time_series=throughput_data if throughput_data else None,
            latency_time_series=rm.time_series_data.get('avg_latency') if rm.time_series_data.get('avg_latency') else None,
            timestamps=timestamps
        )
    
    def generate_json_report(self, output_path: Path) -> Path:
        """
        Generate JSON report with all numerical metrics.
        
        Args:
            output_path: Directory to save the report
            
        Returns:
            Path to the generated JSON file
        """
        metrics = self.extract_metrics()
        
        # Convert to dictionary
        metrics_dict = asdict(metrics)
        
        # Save to JSON
        json_file = output_path / f"numerical_metrics_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(metrics_dict, f, indent=2, default=str)
        
        self.logger.info(f"Numerical JSON report saved to: {json_file}")
        return json_file
    
    def generate_csv_report(self, output_path: Path) -> Path:
        """
        Generate CSV report with key numerical metrics (flattened).
        
        Args:
            output_path: Directory to save the report
            
        Returns:
            Path to the generated CSV file
        """
        metrics = self.extract_metrics()
        
        # Flatten the metrics for CSV (exclude time series and complex nested data)
        flat_metrics = {
            'test_timestamp': metrics.test_timestamp,
            'test_duration_seconds': metrics.test_duration_seconds,
            'test_mode': metrics.test_mode,
            'num_tenants': metrics.num_tenants,
            'num_devices': metrics.num_devices,
            'protocols': ','.join(metrics.protocols),
            'total_messages_sent': metrics.total_messages_sent,
            'total_messages_failed': metrics.total_messages_failed,
            'success_rate_percent': metrics.success_rate_percent,
            'avg_throughput_msg_per_sec': metrics.avg_throughput_msg_per_sec,
            'peak_throughput_msg_per_sec': metrics.peak_throughput_msg_per_sec,
            'latency_avg_ms': metrics.latency_avg_ms,
            'latency_p50_ms': metrics.latency_p50_ms,
            'latency_p95_ms': metrics.latency_p95_ms,
            'latency_p99_ms': metrics.latency_p99_ms,
            'latency_p999_ms': metrics.latency_p999_ms,
            'sla_success_rate_achieved': metrics.sla_success_rate_achieved,
            'sla_p95_latency_achieved': metrics.sla_p95_latency_achieved,
            'sla_p99_latency_achieved': metrics.sla_p99_latency_achieved,
            'peak_memory_mb': metrics.peak_memory_mb,
            'avg_memory_mb': metrics.avg_memory_mb,
            'peak_cpu_percent': metrics.peak_cpu_percent,
            'avg_cpu_percent': metrics.avg_cpu_percent,
            'total_errors': metrics.total_errors,
            'error_rate_percent': metrics.error_rate_percent,
        }
        
        # Add advanced metrics if available
        if metrics.registration_success_rate is not None:
            flat_metrics['registration_success_rate'] = metrics.registration_success_rate
        if metrics.avg_registration_delay_sec is not None:
            flat_metrics['avg_registration_delay_sec'] = metrics.avg_registration_delay_sec
        if metrics.poisson_mean_interval_sec is not None:
            flat_metrics['poisson_mean_interval_sec'] = metrics.poisson_mean_interval_sec
        
        csv_file = output_path / f"numerical_metrics_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=flat_metrics.keys())
            writer.writeheader()
            writer.writerow(flat_metrics)
        
        self.logger.info(f"Numerical CSV report saved to: {csv_file}")
        return csv_file
    
    def generate_time_series_csv(self, output_path: Path) -> Optional[Path]:
        """
        Generate CSV with time series data for detailed analysis.
        
        Args:
            output_path: Directory to save the report
            
        Returns:
            Path to the generated CSV file, or None if no time series data
        """
        rm = self.reporting_manager
        
        if not rm.time_series_data.get('timestamps'):
            self.logger.warning("No time series data available for CSV export")
            return None
        
        # Prepare time series data
        timestamps = rm.time_series_data['timestamps']
        rows = []
        
        for i, ts in enumerate(timestamps):
            row = {
                'timestamp': ts.isoformat() if hasattr(ts, 'isoformat') else str(ts),
                'msg_rate': rm.time_series_data.get('msg_rate', [])[i] if i < len(rm.time_series_data.get('msg_rate', [])) else None,
                'messages_sent': rm.time_series_data.get('messages_sent', [])[i] if i < len(rm.time_series_data.get('messages_sent', [])) else None,
                'messages_failed': rm.time_series_data.get('messages_failed', [])[i] if i < len(rm.time_series_data.get('messages_failed', [])) else None,
                'avg_latency_ms': rm.time_series_data.get('avg_latency', [])[i] if i < len(rm.time_series_data.get('avg_latency', [])) else None,
                'latency_p95_ms': rm.time_series_data.get('latency_95th', [])[i] if i < len(rm.time_series_data.get('latency_95th', [])) else None,
                'latency_p99_ms': rm.time_series_data.get('latency_99th', [])[i] if i < len(rm.time_series_data.get('latency_99th', [])) else None,
                'success_rate_percent': rm.time_series_data.get('success_rate', [])[i] if i < len(rm.time_series_data.get('success_rate', [])) else None,
                'memory_mb': rm.time_series_data.get('memory_usage_mb', [])[i] if i < len(rm.time_series_data.get('memory_usage_mb', [])) else None,
                'cpu_percent': rm.time_series_data.get('cpu_usage_percent', [])[i] if i < len(rm.time_series_data.get('cpu_usage_percent', [])) else None,
            }
            rows.append(row)
        
        csv_file = output_path / f"time_series_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
        
        self.logger.info(f"Time series CSV saved to: {csv_file}")
        return csv_file
    
    def generate_summary_text(self, output_path: Path) -> Path:
        """
        Generate human-readable text summary of numerical metrics.
        
        Args:
            output_path: Directory to save the report
            
        Returns:
            Path to the generated text file
        """
        metrics = self.extract_metrics()
        
        summary = f"""
================================================================================
NUMERICAL METRICS SUMMARY - HONO LOAD TEST
================================================================================

Test Information:
  Timestamp: {metrics.test_timestamp}
  Duration: {metrics.test_duration_seconds:.2f} seconds ({metrics.test_duration_seconds/3600:.2f} hours)
  Mode: {metrics.test_mode}
  Tenants: {metrics.num_tenants}
  Devices: {metrics.num_devices}
  Protocols: {', '.join(metrics.protocols)}

Message Statistics:
  Total Sent: {metrics.total_messages_sent:,}
  Total Failed: {metrics.total_messages_failed:,}
  Success Rate: {metrics.success_rate_percent:.2f}%
  Error Rate: {metrics.error_rate_percent:.2f}%

Throughput Metrics:
  Average: {metrics.avg_throughput_msg_per_sec:.2f} msg/sec
  Peak: {metrics.peak_throughput_msg_per_sec:.2f} msg/sec
  Minimum: {metrics.min_throughput_msg_per_sec:.2f} msg/sec

Latency Metrics (milliseconds):
  Average: {metrics.latency_avg_ms:.2f} ms
  Minimum: {metrics.latency_min_ms:.2f} ms
  Maximum: {metrics.latency_max_ms:.2f} ms
  Std Dev: {metrics.latency_stddev_ms:.2f} ms
  P50: {metrics.latency_p50_ms:.2f} ms
  P95: {metrics.latency_p95_ms:.2f} ms
  P99: {metrics.latency_p99_ms:.2f} ms
  P99.9: {metrics.latency_p999_ms:.2f} ms

SLA Compliance:
  Success Rate Target: {metrics.sla_success_rate_target:.2f}% - {'✅ PASS' if metrics.sla_success_rate_achieved else '❌ FAIL'}
  P95 Latency Target: {metrics.sla_p95_latency_target_ms:.2f} ms - {'✅ PASS' if metrics.sla_p95_latency_achieved else '❌ FAIL'}
  P99 Latency Target: {metrics.sla_p99_latency_target_ms:.2f} ms - {'✅ PASS' if metrics.sla_p99_latency_achieved else '❌ FAIL'}

Resource Usage:
  Peak Memory: {metrics.peak_memory_mb:.2f} MB
  Average Memory: {metrics.avg_memory_mb:.2f} MB
  Peak CPU: {metrics.peak_cpu_percent:.2f}%
  Average CPU: {metrics.avg_cpu_percent:.2f}%

Protocol Breakdown:
"""
        
        for protocol, stats in metrics.protocol_stats.items():
            summary += f"""  {protocol.upper()}:
    Messages Sent: {stats['messages_sent']:,}
    Messages Failed: {stats['messages_failed']:,}
    Success Rate: {stats['success_rate_percent']:.2f}%
    Devices: {stats['devices']}
"""
        
        if metrics.error_types:
            summary += "\nError Type Breakdown:\n"
            for error_type, count in metrics.error_types.items():
                if count > 0:
                    summary += f"  {error_type.replace('_', ' ').title()}: {count:,}\n"
        
        if metrics.registration_success_rate is not None:
            summary += f"\nAdvanced Metrics:\n"
            summary += f"  Registration Success Rate: {metrics.registration_success_rate:.2f}%\n"
            if metrics.avg_registration_delay_sec is not None:
                summary += f"  Avg Registration Delay: {metrics.avg_registration_delay_sec:.2f} sec\n"
            if metrics.poisson_mean_interval_sec is not None:
                summary += f"  Poisson Mean Interval: {metrics.poisson_mean_interval_sec:.2f} sec\n"
            if metrics.poisson_coefficient_of_variation is not None:
                summary += f"  Poisson CV: {metrics.poisson_coefficient_of_variation:.3f}\n"
        
        summary += "\n================================================================================\n"
        
        text_file = output_path / f"numerical_summary_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(summary)
        
        self.logger.info(f"Numerical summary saved to: {text_file}")
        return text_file
    
    def generate_all_reports(self, output_path: Path) -> Dict[str, Path]:
        """
        Generate all numerical report formats.
        
        Args:
            output_path: Directory to save the reports
            
        Returns:
            Dictionary mapping report type to file path
        """
        reports = {}
        
        try:
            reports['json'] = self.generate_json_report(output_path)
        except Exception as e:
            self.logger.error(f"Failed to generate JSON report: {e}")
        
        try:
            reports['csv'] = self.generate_csv_report(output_path)
        except Exception as e:
            self.logger.error(f"Failed to generate CSV report: {e}")
        
        try:
            time_series_csv = self.generate_time_series_csv(output_path)
            if time_series_csv:
                reports['time_series_csv'] = time_series_csv
        except Exception as e:
            self.logger.error(f"Failed to generate time series CSV: {e}")
        
        try:
            reports['summary'] = self.generate_summary_text(output_path)
        except Exception as e:
            self.logger.error(f"Failed to generate summary text: {e}")
        
        return reports
