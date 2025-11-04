"""
Device model for Hono Load Test Suite.
Contains the Device dataclass representing a device in the load test.
"""

from dataclasses import dataclass


@dataclass
class Device:
    """Represents a device in the load test."""
    device_id: str
    tenant_id: str
    password: str
    auth_id: str = None
    
    def __post_init__(self):
        if self.auth_id is None:
            self.auth_id = self.device_id
