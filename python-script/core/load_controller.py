
import time
import logging
import threading
from typing import Optional, Dict, Any

class LoadController:
    """
    Manages dynamic load control, including burst mode and rate adjustments.
    Thread-safe controller that workers consult for current sleep intervals.
    """

    def __init__(self, base_interval: float, config: Dict[str, Any] = None):
        self.logger = logging.getLogger(__name__)
        self.base_interval = base_interval
        self.current_interval = base_interval
        self.config = config or {}
        
        # Burst configuration
        self.burst_enabled = False
        self.burst_multiplier = 1.0
        self.burst_duration = 0
        self.burst_frequency = 0
        
        self._running = False
        self._burst_active = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._parse_config()

    def _parse_config(self):
        """Parse burst configuration."""
        burst_config = self.config.get('burst', {})
        if burst_config.get('enabled', False):
            self.burst_enabled = True
            self.burst_multiplier = float(burst_config.get('multiplier', 5.0))
            self.burst_duration = int(burst_config.get('duration_sec', 60))
            self.burst_frequency = int(burst_config.get('frequency_sec', 600))
            self.logger.info(f"LoadController: Burst mode ENABLED (x{self.burst_multiplier} for {self.burst_duration}s every {self.burst_frequency}s)")
        else:
            self.logger.info("LoadController: Burst mode DISABLED")

    def start(self):
        """Start the load controller scheduler."""
        if self.burst_enabled and not self._running:
            self._running = True
            self._scheduler_thread = threading.Thread(target=self._burst_scheduler_loop, daemon=True, name="LoadController-Scheduler")
            self._scheduler_thread.start()
            self.logger.info("LoadController: Scheduler started")

    def stop(self):
        """Stop the load controller."""
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=2.0)
            self.logger.info("LoadController: Scheduler stopped")

    def get_current_interval(self) -> float:
        """Get the current message interval to use."""
        # Simple read, atomic enough for float in Python
        return self.current_interval

    def is_burst_active(self) -> bool:
        """Check if burst mode is currently active."""
        return self._burst_active

    def _burst_scheduler_loop(self):
        """Loop to manage burst timing."""
        last_burst_time = time.time()
        
        while self._running:
            now = time.time()
            time_since_last = now - last_burst_time
            
            if not self._burst_active:
                # Check if it's time to start a burst
                if time_since_last >= self.burst_frequency:
                    self._start_burst()
                    last_burst_time = now # Reset timer
            else:
                # Check if it's time to end the burst
                if time_since_last >= self.burst_duration:
                    self._end_burst()
                    last_burst_time = time.time() # Reset timer for next cycle
            
            time.sleep(1.0) # Check every second

    def _start_burst(self):
        """Activate burst mode."""
        with self._lock:
            self._burst_active = True
            self.current_interval = self.base_interval / self.burst_multiplier
            self.logger.info(f">>> BURST STARTED! Interval reduced to {self.current_interval:.4f}s (x{self.burst_multiplier} load) <<<")

    def _end_burst(self):
        """Deactivate burst mode."""
        with self._lock:
            self._burst_active = False
            self.current_interval = self.base_interval
            self.logger.info(f"<<< BURST ENDED. Interval restored to {self.current_interval:.4f}s >>>")
