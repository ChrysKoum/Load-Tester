"""
Smart Logging Module for Hono Load Test Suite.
Implements intelligent logging that reduces log file size while maintaining critical information.
"""

import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from collections import deque


@dataclass
class SmartLoggerConfig:
    """Configuration for smart logging behavior."""
    # Initial iterations to log (verify everything works)
    initial_log_count: int = 10
    
    # After failure, log N more iterations to check stabilization
    post_failure_log_count: int = 5
    
    # Periodic logging interval (calculated from total time if not set)
    periodic_interval: Optional[int] = None
    
    # Total test duration in seconds (used to calculate periodic_interval)
    total_duration_seconds: Optional[float] = None
    
    # Default periodic interval divisor (TOTAL_TIME / 50)
    periodic_divisor: int = 50
    
    # Enable/disable smart logging
    enabled: bool = True


class SmartLogger:
    """
    Smart logger that reduces log verbosity while maintaining critical information.
    
    Logging Strategy:
    1. Log first N iterations to verify system works
    2. After success, only log failures + M iterations after failure
    3. Periodically log every K iterations (configurable, default: TOTAL_TIME / 50)
    """
    
    def __init__(self, config: SmartLoggerConfig, logger_name: str = "smart_logger"):
        self.config = config
        self.logger = logging.getLogger(logger_name)
        
        # State tracking
        self.iteration_count = 0
        self.initial_phase = True
        self.last_failure_iteration = -1
        self.failure_count = 0
        self.success_count = 0
        
        # Calculate periodic interval if not set
        if self.config.periodic_interval is None and self.config.total_duration_seconds:
            # Calculate how many iterations we expect
            # Assuming ~1 iteration per second as baseline
            expected_iterations = int(self.config.total_duration_seconds)
            self.config.periodic_interval = max(1, expected_iterations // self.config.periodic_divisor)
        elif self.config.periodic_interval is None:
            # Default fallback
            self.config.periodic_interval = 100
        
        self.logger.info(
            f"SmartLogger initialized: initial_log={self.config.initial_log_count}, "
            f"post_failure_log={self.config.post_failure_log_count}, "
            f"periodic_interval={self.config.periodic_interval}"
        )
    
    def should_log(self, is_success: bool = True) -> bool:
        """
        Determine if current iteration should be logged.
        
        Args:
            is_success: Whether the current operation succeeded
            
        Returns:
            True if this iteration should be logged
        """
        if not self.config.enabled:
            return True  # Log everything if smart logging is disabled
        
        self.iteration_count += 1
        
        # Phase 1: Initial logging (first N iterations)
        if self.initial_phase:
            if self.iteration_count <= self.config.initial_log_count:
                if is_success:
                    self.success_count += 1
                else:
                    self.failure_count += 1
                return True
            else:
                # Exit initial phase
                self.initial_phase = False
                self.logger.info(
                    f"SmartLogger: Initial phase complete. "
                    f"Success: {self.success_count}, Failures: {self.failure_count}. "
                    f"Switching to smart logging mode."
                )
        
        # Phase 2: Smart logging
        
        # Always log failures
        if not is_success:
            self.failure_count += 1
            self.last_failure_iteration = self.iteration_count
            self.logger.warning(
                f"SmartLogger: Failure detected at iteration {self.iteration_count}. "
                f"Will log next {self.config.post_failure_log_count} iterations."
            )
            return True
        
        # Log N iterations after a failure (stabilization check)
        iterations_since_failure = self.iteration_count - self.last_failure_iteration
        if 0 < iterations_since_failure <= self.config.post_failure_log_count:
            self.success_count += 1
            if iterations_since_failure == self.config.post_failure_log_count:
                self.logger.info(
                    f"SmartLogger: Stabilization period complete after failure. "
                    f"Resuming periodic logging."
                )
            return True
        
        # Periodic logging
        if self.iteration_count % self.config.periodic_interval == 0:
            self.success_count += 1
            return True
        
        # Don't log this iteration
        self.success_count += 1
        return False
    
    def log_message(self, level: int, message: str, is_success: bool = True, **kwargs):
        """
        Log a message if smart logging rules allow it.
        
        Args:
            level: Logging level (logging.INFO, logging.WARNING, etc.)
            message: Message to log
            is_success: Whether this represents a successful operation
            **kwargs: Additional context to include in log
        """
        if self.should_log(is_success):
            extra_info = f" [{', '.join(f'{k}={v}' for k, v in kwargs.items())}]" if kwargs else ""
            self.logger.log(level, f"{message}{extra_info}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current logging statistics."""
        return {
            'total_iterations': self.iteration_count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'initial_phase': self.initial_phase,
            'periodic_interval': self.config.periodic_interval,
            'log_reduction_ratio': 1.0 - (self.config.periodic_interval / max(1, self.iteration_count))
            if self.iteration_count > self.config.initial_log_count else 0.0
        }
    
    def force_log(self, level: int, message: str, **kwargs):
        """Force log a message regardless of smart logging rules."""
        extra_info = f" [{', '.join(f'{k}={v}' for k, v in kwargs.items())}]" if kwargs else ""
        self.logger.log(level, f"[FORCED] {message}{extra_info}")


class MessageLogger:
    """
    Specialized logger for message transmission events.
    Integrates with SmartLogger for intelligent logging.
    """
    
    def __init__(self, smart_logger: SmartLogger):
        self.smart_logger = smart_logger
        self.logger = logging.getLogger("message_logger")
    
    def log_send_attempt(self, device_id: str, protocol: str, success: bool, 
                        latency_ms: Optional[float] = None, error: Optional[str] = None):
        """Log a message send attempt."""
        if success:
            msg = f"Message sent successfully: device={device_id}, protocol={protocol}"
            if latency_ms is not None:
                msg += f", latency={latency_ms:.2f}ms"
            self.smart_logger.log_message(
                logging.INFO, msg, is_success=True,
                device=device_id, protocol=protocol, latency=latency_ms
            )
        else:
            msg = f"Message send FAILED: device={device_id}, protocol={protocol}"
            if error:
                msg += f", error={error}"
            self.smart_logger.log_message(
                logging.ERROR, msg, is_success=False,
                device=device_id, protocol=protocol, error=error
            )
    
    def log_connection_event(self, device_id: str, protocol: str, event_type: str, 
                            success: bool, details: Optional[str] = None):
        """Log connection-related events."""
        msg = f"Connection {event_type}: device={device_id}, protocol={protocol}"
        if details:
            msg += f", details={details}"
        
        level = logging.INFO if success else logging.WARNING
        self.smart_logger.log_message(
            level, msg, is_success=success,
            device=device_id, protocol=protocol, event=event_type
        )


def create_smart_logger(total_duration_seconds: Optional[float] = None,
                       initial_log_count: int = 10,
                       post_failure_log_count: int = 5,
                       periodic_divisor: int = 50,
                       enabled: bool = True) -> SmartLogger:
    """
    Factory function to create a configured SmartLogger.
    
    Args:
        total_duration_seconds: Total expected test duration in seconds
        initial_log_count: Number of initial iterations to log
        post_failure_log_count: Number of iterations to log after a failure
        periodic_divisor: Divisor for calculating periodic interval (TOTAL_TIME / divisor)
        enabled: Whether smart logging is enabled
        
    Returns:
        Configured SmartLogger instance
    """
    config = SmartLoggerConfig(
        initial_log_count=initial_log_count,
        post_failure_log_count=post_failure_log_count,
        total_duration_seconds=total_duration_seconds,
        periodic_divisor=periodic_divisor,
        enabled=enabled
    )
    
    return SmartLogger(config)
