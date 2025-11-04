"""
Device and Tenant Cache Management for Hono Load Test Suite.
Stores and retrieves device/tenant information to avoid recreating them.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from models.device import Device


class DeviceCache:
    """Manages caching of tenants and devices for specific Hono server IPs."""
    
    def __init__(self, cache_dir: str = "./cache"):
        """
        Initialize the device cache.
        
        Args:
            cache_dir: Directory where cache files will be stored
        """
        self.logger = logging.getLogger(__name__)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.logger.debug(f"Device cache initialized at: {self.cache_dir.absolute()}")
    
    def _get_cache_file(self, registry_ip: str, registry_port: int) -> Path:
        """
        Get the cache file path for a specific server.
        
        Args:
            registry_ip: Registry server IP/hostname
            registry_port: Registry server port
            
        Returns:
            Path to the cache file
        """
        # Sanitize the IP/hostname for filename
        safe_name = registry_ip.replace(":", "_").replace("/", "_")
        cache_filename = f"devices_{safe_name}_{registry_port}.json"
        return self.cache_dir / cache_filename
    
    def load_cache(self, registry_ip: str, registry_port: int) -> Optional[Dict]:
        """
        Load cached tenants and devices for a specific server.
        
        Args:
            registry_ip: Registry server IP/hostname
            registry_port: Registry server port
            
        Returns:
            Dictionary with tenants and devices, or None if cache doesn't exist
        """
        cache_file = self._get_cache_file(registry_ip, registry_port)
        
        if not cache_file.exists():
            self.logger.info(f"No cache found for {registry_ip}:{registry_port}")
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            self.logger.info(f"✅ Loaded cache for {registry_ip}:{registry_port}")
            self.logger.info(f"   Tenants: {len(cache_data.get('tenants', []))}")
            self.logger.info(f"   Devices: {len(cache_data.get('devices', []))}")
            
            return cache_data
        
        except Exception as e:
            self.logger.error(f"Failed to load cache from {cache_file}: {e}")
            return None
    
    def save_cache(self, registry_ip: str, registry_port: int, 
                   tenants: List[str], devices: List[Device]) -> bool:
        """
        Save tenants and devices to cache for a specific server.
        
        Args:
            registry_ip: Registry server IP/hostname
            registry_port: Registry server port
            tenants: List of tenant IDs
            devices: List of Device objects
            
        Returns:
            True if saved successfully, False otherwise
        """
        cache_file = self._get_cache_file(registry_ip, registry_port)
        
        try:
            # Convert devices to serializable format
            devices_data = []
            for device in devices:
                devices_data.append({
                    'device_id': device.device_id,
                    'tenant_id': device.tenant_id,
                    'password': device.password,
                    'auth_id': device.auth_id
                })
            
            cache_data = {
                'server': {
                    'registry_ip': registry_ip,
                    'registry_port': registry_port
                },
                'cached_at': datetime.now().isoformat(),
                'tenants': tenants,
                'devices': devices_data
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            
            self.logger.info(f"💾 Saved cache to {cache_file}")
            self.logger.info(f"   Tenants: {len(tenants)}")
            self.logger.info(f"   Devices: {len(devices)}")
            
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to save cache to {cache_file}: {e}")
            return False
    
    def devices_from_cache(self, cache_data: Dict) -> List[Device]:
        """
        Convert cached device data back to Device objects.
        
        Args:
            cache_data: Dictionary containing cached data
            
        Returns:
            List of Device objects
        """
        devices = []
        for device_data in cache_data.get('devices', []):
            device = Device(
                device_id=device_data['device_id'],
                tenant_id=device_data['tenant_id'],
                password=device_data['password'],
                auth_id=device_data.get('auth_id', device_data['device_id'])
            )
            devices.append(device)
        
        return devices
    
    def get_devices(self, registry_ip: str, registry_port: int, 
                    count: int) -> Optional[List[Device]]:
        """
        Get devices from cache. Returns None if not enough devices available.
        
        Args:
            registry_ip: Registry server IP/hostname
            registry_port: Registry server port
            count: Number of devices needed
            
        Returns:
            List of Device objects if enough available, None otherwise
        """
        cache_data = self.load_cache(registry_ip, registry_port)
        
        if not cache_data:
            return None
        
        devices = self.devices_from_cache(cache_data)
        
        if len(devices) < count:
            self.logger.warning(f"Cache has {len(devices)} devices, but {count} requested")
            return None
        
        # Return the requested number of devices
        selected_devices = devices[:count]
        self.logger.info(f"📤 Using {count} devices from cache")
        return selected_devices
    
    def clear_cache(self, registry_ip: str, registry_port: int) -> bool:
        """
        Clear cache for a specific server.
        
        Args:
            registry_ip: Registry server IP/hostname
            registry_port: Registry server port
            
        Returns:
            True if cleared successfully, False otherwise
        """
        cache_file = self._get_cache_file(registry_ip, registry_port)
        
        try:
            if cache_file.exists():
                cache_file.unlink()
                self.logger.info(f"🗑️  Cleared cache for {registry_ip}:{registry_port}")
                return True
            else:
                self.logger.warning(f"No cache file found to clear: {cache_file}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to clear cache: {e}")
            return False
    
    def list_caches(self) -> List[Dict]:
        """
        List all available caches.
        
        Returns:
            List of dictionaries with cache information
        """
        caches = []
        
        for cache_file in self.cache_dir.glob("devices_*.json"):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                caches.append({
                    'file': cache_file.name,
                    'server': cache_data.get('server', {}),
                    'cached_at': cache_data.get('cached_at'),
                    'tenants_count': len(cache_data.get('tenants', [])),
                    'devices_count': len(cache_data.get('devices', []))
                })
            except Exception as e:
                self.logger.warning(f"Failed to read cache file {cache_file}: {e}")
        
        return caches
