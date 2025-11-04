"""
Configuration loader for Hono Load Test Suite.
Loads YAML configuration files and provides easy access to settings and profiles.
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Load and manage configuration from YAML files."""
    
    def __init__(self, config_file: str = "config/hono.yaml"):
        """
        Initialize the config loader.
        
        Args:
            config_file: Path to the YAML configuration file
        """
        self.config_file = Path(config_file)
        self.config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load the main configuration file."""
        if not self.config_file.exists():
            # Try alternative paths
            alternative_paths = [
                Path("config/hono.yaml"),
                Path("../config/hono.yaml"),
                Path("./hono.yaml"),
            ]
            
            for alt_path in alternative_paths:
                if alt_path.exists():
                    self.config_file = alt_path
                    break
            else:
                raise FileNotFoundError(
                    f"Config file not found: {self.config_file}\n"
                    f"Tried: {', '.join(str(p) for p in alternative_paths)}\n"
                    f"Please create config/hono.yaml or use config/hono.example.yaml as template"
                )
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f) or {}
            logger.info(f"Loaded configuration from {self.config_file}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}")
        except Exception as e:
            raise RuntimeError(f"Error loading config file: {e}")
    
    def get_profile(self, profile_name: str) -> Dict[str, Any]:
        """
        Get a specific test profile configuration.
        
        Args:
            profile_name: Name of the profile to load
            
        Returns:
            Dictionary containing the profile configuration
            
        Raises:
            ValueError: If profile not found
        """
        profiles = self.config.get('profiles', {})
        
        if profile_name not in profiles:
            available = ', '.join(profiles.keys())
            raise ValueError(
                f"Profile '{profile_name}' not found in config.\n"
                f"Available profiles: {available}"
            )
        
        # Start with default test settings
        defaults = self.config.get('test', {})
        profile = profiles[profile_name].copy()
        
        # Merge: defaults first, then profile overrides
        merged = {**defaults, **profile}
        
        logger.info(f"Loaded profile: {profile_name}")
        if 'description' in profile:
            logger.info(f"  Description: {profile['description']}")
        
        return merged
    
    def list_profiles(self) -> List[str]:
        """
        Get list of all available profile names.
        
        Returns:
            List of profile names
        """
        return list(self.config.get('profiles', {}).keys())
    
    def get_profile_info(self, profile_name: str) -> str:
        """
        Get human-readable information about a profile.
        
        Args:
            profile_name: Name of the profile
            
        Returns:
            Formatted string with profile details
        """
        try:
            profile = self.get_profile(profile_name)
            info = [f"Profile: {profile_name}"]
            
            if 'description' in profile:
                info.append(f"  Description: {profile['description']}")
            
            info.append(f"  Tenants: {profile.get('tenants', 'N/A')}")
            info.append(f"  Devices: {profile.get('devices', 'N/A')}")
            info.append(f"  Protocols: {', '.join(profile.get('protocols', []))}")
            info.append(f"  Message Interval: {profile.get('message_interval', 'N/A')}s")
            info.append(f"  Duration: {profile.get('duration', 'N/A')}s")
            
            if 'notes' in profile:
                info.append(f"  Notes: {profile['notes']}")
            
            return '\n'.join(info)
        except ValueError as e:
            return str(e)
    
    def get_server_config(self) -> Dict[str, Any]:
        """
        Get server configuration (registry and adapters).
        
        Returns:
            Dictionary with server settings
        """
        return self.config.get('server', {})
    
    def get_security_config(self) -> Dict[str, Any]:
        """
        Get security configuration (TLS, certificates, auth).
        
        Returns:
            Dictionary with security settings
        """
        return self.config.get('security', {})
    
    def get_cache_config(self) -> Dict[str, Any]:
        """
        Get caching configuration.
        
        Returns:
            Dictionary with cache settings
        """
        return self.config.get('cache', {})
    
    def get_reporting_config(self) -> Dict[str, Any]:
        """
        Get reporting configuration.
        
        Returns:
            Dictionary with reporting settings
        """
        return self.config.get('reporting', {})
    
    def get_limits_config(self) -> Dict[str, Any]:
        """
        Get resource limits configuration.
        
        Returns:
            Dictionary with resource limit settings
        """
        return self.config.get('limits', {})
    
    def get_advanced_config(self) -> Dict[str, Any]:
        """
        Get advanced features configuration.
        
        Returns:
            Dictionary with advanced settings
        """
        return self.config.get('advanced', {})
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """
        Get monitoring configuration.
        
        Returns:
            Dictionary with monitoring settings
        """
        return self.config.get('monitoring', {})
    
    def apply_overrides(self, profile: Dict[str, Any], **overrides) -> Dict[str, Any]:
        """
        Apply CLI argument overrides to a profile configuration.
        
        Args:
            profile: Base profile configuration
            **overrides: Keyword arguments to override (only non-None values are applied)
            
        Returns:
            Profile with overrides applied
        """
        result = profile.copy()
        
        for key, value in overrides.items():
            if value is not None:  # Only override if explicitly set
                # Handle special cases
                if key == 'protocols' and isinstance(value, str):
                    # Convert comma-separated string to list
                    result[key] = [p.strip() for p in value.split(',')]
                else:
                    result[key] = value
                logger.debug(f"Override: {key} = {value}")
        
        return result
    
    def get_full_config(
        self,
        profile_name: str,
        **overrides
    ) -> Dict[str, Any]:
        """
        Get complete configuration with profile and overrides.
        Convenience method that combines profile loading and override application.
        
        Args:
            profile_name: Name of the profile to use
            **overrides: CLI argument overrides
            
        Returns:
            Complete configuration dictionary
        """
        # Get base profile
        profile = self.get_profile(profile_name)
        
        # Apply overrides
        profile = self.apply_overrides(profile, **overrides)
        
        # Build complete config
        complete_config = {
            'profile_name': profile_name,
            'test': profile,
            'server': self.get_server_config(),
            'security': self.get_security_config(),
            'cache': self.get_cache_config(),
            'reporting': self.get_reporting_config(),
            'limits': self.get_limits_config(),
            'advanced': self.get_advanced_config(),
            'monitoring': self.get_monitoring_config(),
        }
        
        return complete_config
    
    def validate_config(self) -> List[str]:
        """
        Validate the configuration file for common issues.
        
        Returns:
            List of validation warnings/errors (empty if valid)
        """
        issues = []
        
        # Check required sections
        required_sections = ['server', 'profiles']
        for section in required_sections:
            if section not in self.config:
                issues.append(f"Missing required section: {section}")
        
        # Check server config
        server = self.config.get('server', {})
        if 'registry' not in server:
            issues.append("Missing server.registry configuration")
        
        # Check profiles
        profiles = self.config.get('profiles', {})
        if not profiles:
            issues.append("No test profiles defined")
        
        # Validate each profile
        for name, profile in profiles.items():
            if 'tenants' not in profile and 'tenants' not in self.config.get('test', {}):
                issues.append(f"Profile '{name}': missing 'tenants' setting")
            if 'devices' not in profile and 'devices' not in self.config.get('test', {}):
                issues.append(f"Profile '{name}': missing 'devices' setting")
        
        return issues
    
    def print_summary(self) -> None:
        """Print a summary of the loaded configuration."""
        print("=" * 60)
        print("Hono Load Test Configuration")
        print("=" * 60)
        
        # Server info
        server = self.get_server_config()
        if 'registry' in server:
            reg = server['registry']
            print(f"Server: {reg.get('host', 'N/A')}:{reg.get('port', 'N/A')}")
        
        # Cache info
        cache = self.get_cache_config()
        print(f"Cache: {'Enabled' if cache.get('enabled') else 'Disabled'}")
        
        # Profiles
        profiles = self.list_profiles()
        print(f"\nAvailable Profiles ({len(profiles)}):")
        for profile_name in sorted(profiles):
            profile_config = self.config['profiles'][profile_name]
            desc = profile_config.get('description', 'No description')
            print(f"  - {profile_name:20s} : {desc}")
        
        print("=" * 60)


def load_config(config_file: str = "config/hono.yaml") -> ConfigLoader:
    """
    Convenience function to load configuration.
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        ConfigLoader instance
    """
    return ConfigLoader(config_file)


# Example usage
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Load config
        config = load_config()
        
        # Print summary
        config.print_summary()
        
        # Show validation
        issues = config.validate_config()
        if issues:
            print("\n⚠️ Configuration Issues:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("\n✅ Configuration is valid")
        
        # Example: Load a profile
        print("\n" + "=" * 60)
        print("Example: Loading 'smoke' profile")
        print("=" * 60)
        smoke_config = config.get_full_config('smoke')
        print(f"Tenants: {smoke_config['test']['tenants']}")
        print(f"Devices: {smoke_config['test']['devices']}")
        print(f"Protocols: {smoke_config['test']['protocols']}")
        
        # Example: With overrides
        print("\n" + "=" * 60)
        print("Example: Overriding profile settings")
        print("=" * 60)
        custom_config = config.get_full_config(
            'smoke',
            devices=5,
            protocols='mqtt,http',
            duration=120
        )
        print(f"Tenants: {custom_config['test']['tenants']}")
        print(f"Devices: {custom_config['test']['devices']} (overridden)")
        print(f"Protocols: {custom_config['test']['protocols']} (overridden)")
        print(f"Duration: {custom_config['test']['duration']}s (overridden)")
        
    except Exception as e:
        print(f"❌ Error: {e}")
