"""
Test modes configuration for Hono Load Test Suite.
Defines various test scenarios from light load to stress testing, including long-duration tests.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum


class TestIntensity(Enum):
    """Test intensity levels."""
    MINIMAL = "minimal"
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"
    STRESS = "stress"
    EXTREME = "extreme"
    ENDURANCE = "endurance"
    CUSTOM = "custom"


@dataclass
class TestMode:
    """Configuration for a specific test mode."""
    name: str
    description: str
    tenants: int
    devices: int
    protocols: List[str]
    message_interval: float  # seconds between messages
    duration_hint: str       # expected test duration
    intensity: TestIntensity
    recommended_hardware: str
    notes: str
    expected_rps: str        # expected requests per second
    memory_usage: str        # expected memory usage
    target_duration_hours: float = 0.0  # For endurance tests
    # Add new fields for custom mode features
    enable_poisson: bool = False
    enable_throttling: bool = False
    throttling_base_delay: Any = None # Or a sensible default like 0.5
    throttling_jitter: Any = None     # Or a sensible default like 0.2
    generate_report: bool = False


# Define comprehensive test modes with variations from 1-150 devices
TEST_MODES: Dict[str, TestMode] = {
    "smoke": TestMode(
        name="Smoke Test",
        description="Minimal connectivity test with single device",
        tenants=1,
        devices=1,
        protocols=["mqtt"],
        message_interval=30.0,
        duration_hint="1-2 minutes",
        intensity=TestIntensity.MINIMAL,
        recommended_hardware="Any system",
        notes="Perfect for initial setup validation and connectivity checks",
        expected_rps="0.03 req/sec",
        memory_usage="< 50 MB"
    ),
    
    "dev": TestMode(
        name="Development Test",
        description="Light development testing with minimal load",
        tenants=1,
        devices=2,
        protocols=["mqtt"],
        message_interval=15.0,
        duration_hint="2-5 minutes",
        intensity=TestIntensity.MINIMAL,
        recommended_hardware="Development laptop",
        notes="Ideal for development and debugging scenarios",
        expected_rps="0.13 req/sec",
        memory_usage="< 100 MB"
    ),
    
    "quick": TestMode(
        name="Quick Validation",
        description="Fast validation test with multiple protocols",
        tenants=2,
        devices=5,
        protocols=["mqtt", "http"],
        message_interval=10.0,
        duration_hint="3-5 minutes",
        intensity=TestIntensity.LIGHT,
        recommended_hardware="Standard development machine",
        notes="Quick multi-protocol validation for CI/CD pipelines",
        expected_rps="0.5 req/sec",
        memory_usage="< 150 MB"
    ),
    
    "light": TestMode(
        name="Light Load Test",
        description="Light production-like load testing",
        tenants=3,
        devices=10,
        protocols=["mqtt", "http"],
        message_interval=8.0,
        duration_hint="10-15 minutes",
        intensity=TestIntensity.LIGHT,
        recommended_hardware="2-4 CPU cores, 4GB RAM",
        notes="Simulates light IoT deployment with mixed protocols",
        expected_rps="1.25 req/sec",
        memory_usage="< 300 MB"
    ),
    
    "small": TestMode(
        name="Small Scale Test",
        description="Small office/home IoT deployment simulation",
        tenants=4,
        devices=15,
        protocols=["mqtt", "http"],
        message_interval=7.0,
        duration_hint="15-20 minutes",
        intensity=TestIntensity.LIGHT,
        recommended_hardware="4 CPU cores, 4GB RAM",
        notes="Typical small office or smart home deployment",
        expected_rps="2.1 req/sec",
        memory_usage="< 400 MB"
    ),
    
    "standard": TestMode(
        name="Standard Load Test",
        description="Standard production load simulation",
        tenants=5,
        devices=25,
        protocols=["mqtt", "http"],
        message_interval=6.0,
        duration_hint="15-30 minutes",
        intensity=TestIntensity.MODERATE,
        recommended_hardware="4-8 CPU cores, 8GB RAM",
        notes="Typical IoT production load with moderate device density",
        expected_rps="4.2 req/sec",
        memory_usage="< 500 MB"
    ),
    
    "business": TestMode(
        name="Business Scale Test",
        description="Business/enterprise IoT deployment",
        tenants=6,
        devices=40,
        protocols=["mqtt", "http"],
        message_interval=5.5,
        duration_hint="20-40 minutes",
        intensity=TestIntensity.MODERATE,
        recommended_hardware="8 CPU cores, 12GB RAM",
        notes="Medium business IoT deployment with multiple tenants",
        expected_rps="7.3 req/sec",
        memory_usage="< 800 MB"
    ),
    
    "medium": TestMode(
        name="Medium Scale Test",
        description="Medium scale deployment simulation",
        tenants=8,
        devices=50,
        protocols=["mqtt", "http"],
        message_interval=5.0,
        duration_hint="20-45 minutes",
        intensity=TestIntensity.MODERATE,
        recommended_hardware="8+ CPU cores, 16GB RAM",
        notes="Medium enterprise IoT deployment simulation",
        expected_rps="10 req/sec",
        memory_usage="< 1 GB"
    ),
    
    "enterprise": TestMode(
        name="Enterprise Scale Test",
        description="Large enterprise IoT deployment",
        tenants=10,
        devices=65,
        protocols=["mqtt", "http"],
        message_interval=4.0,
        duration_hint="25-50 minutes",
        intensity=TestIntensity.HEAVY,
        recommended_hardware="12+ CPU cores, 24GB RAM",
        notes="Large enterprise deployment with multiple protocols",
        expected_rps="16.3 req/sec",
        memory_usage="< 1.5 GB"
    ),
    
    "heavy": TestMode(
        name="Heavy Load Test",
        description="Heavy production load with high message frequency",
        tenants=10,
        devices=75,
        protocols=["mqtt", "http"],
        message_interval=3.0,
        duration_hint="30-60 minutes",
        intensity=TestIntensity.HEAVY,
        recommended_hardware="16+ CPU cores, 32GB RAM",
        notes="Heavy production load testing for high-throughput scenarios",
        expected_rps="25 req/sec",
        memory_usage="< 2 GB"
    ),
    
    "stress": TestMode(
        name="Stress Test",
        description="High-stress testing with maximum device count",
        tenants=15,
        devices=100,
        protocols=["mqtt", "http"],
        message_interval=2.0,
        duration_hint="45-90 minutes",
        intensity=TestIntensity.STRESS,
        recommended_hardware="24+ CPU cores, 64GB RAM, SSD storage",
        notes="Stress testing to find system limits and breaking points",
        expected_rps="50 req/sec",
        memory_usage="< 4 GB"
    ),
    
    "burst": TestMode(
        name="Burst Load Test",
        description="Burst traffic simulation with rapid message intervals",
        tenants=5,
        devices=30,
        protocols=["mqtt", "http"],
        message_interval=1.0,
        duration_hint="10-20 minutes",
        intensity=TestIntensity.HEAVY,
        recommended_hardware="16+ CPU cores, 32GB RAM",
        notes="Simulates burst traffic patterns and peak load scenarios",
        expected_rps="30 req/sec",
        memory_usage="< 1.5 GB"
    ),
    
    "extreme": TestMode(
        name="Extreme Scale Test",
        description="Maximum scale testing for enterprise deployments",
        tenants=20,
        devices=150,
        protocols=["mqtt", "http"],
        message_interval=1.5,
        duration_hint="60-120 minutes",
        intensity=TestIntensity.EXTREME,
        recommended_hardware="32+ CPU cores, 128GB RAM, High-speed network",
        notes="Enterprise-scale testing for large IoT deployments. Monitor system resources carefully.",
        expected_rps="100 req/sec",
        memory_usage="< 8 GB"
    ),
    
    # NEW: One-day endurance test as requested
    "oneday": TestMode(
        name="One Day Endurance Test",
        description="24-hour endurance test with 100 devices and 10 tenants",
        tenants=10,
        devices=100,
        protocols=["mqtt", "http"],
        message_interval=5.5,
        duration_hint="24 hours",
        intensity=TestIntensity.ENDURANCE,
        recommended_hardware="32+ CPU cores, 64GB RAM, SSD storage, UPS",
        notes="Long-duration test to validate system stability over 24 hours. Monitor disk space and memory leaks.",
        expected_rps="18.2 req/sec",
        memory_usage="< 4 GB",
        target_duration_hours=24.0
    ),
    
    # Additional endurance tests
    "halfday": TestMode(
        name="Half Day Endurance Test",
        description="12-hour endurance test with moderate load",
        tenants=8,
        devices=60,
        protocols=["mqtt", "http"],
        message_interval=6.0,
        duration_hint="12 hours",
        intensity=TestIntensity.ENDURANCE,
        recommended_hardware="16+ CPU cores, 32GB RAM, SSD storage",
        notes="12-hour stability test for production readiness validation",
        expected_rps="10 req/sec",
        memory_usage="< 2 GB",
        target_duration_hours=12.0
    ),
    
    "weekend": TestMode(
        name="Weekend Long Test",
        description="48-hour weekend endurance test",
        tenants=12,
        devices=80,
        protocols=["mqtt", "http"],
        message_interval=7.0,
        duration_hint="48 hours",
        intensity=TestIntensity.ENDURANCE,
        recommended_hardware="32+ CPU cores, 128GB RAM, Enterprise SSD, UPS",
        notes="Extended weekend test for long-term stability validation. Requires monitoring.",
        expected_rps="11.4 req/sec",
        memory_usage="< 6 GB",
        target_duration_hours=48.0
    ),
    
    # Protocol-specific test modes
    "mqtt_only": TestMode(
        name="MQTT Only Test",
        description="MQTT protocol focused testing",
        tenants=8,
        devices=50,
        protocols=["mqtt"],
        message_interval=4.0,
        duration_hint="30-45 minutes",
        intensity=TestIntensity.MODERATE,
        recommended_hardware="8+ CPU cores, 16GB RAM",
        notes="Pure MQTT testing for protocol-specific validation and optimization",
        expected_rps="12.5 req/sec",
        memory_usage="< 1 GB"
    ),
    
    "http_only": TestMode(
        name="HTTP Only Test",
        description="HTTP protocol focused testing",
        tenants=8,
        devices=50,
        protocols=["http"],
        message_interval=4.0,
        duration_hint="30-45 minutes",
        intensity=TestIntensity.MODERATE,
        recommended_hardware="8+ CPU cores, 16GB RAM",
        notes="Pure HTTP testing for REST API validation and performance",
        expected_rps="12.5 req/sec",
        memory_usage="< 1 GB"
    ),

    # NEW CUSTOM MODE BASED ON USER COMMAND
    "custom_http_poisson_throttled": TestMode(
        name="Custom HTTP Poisson Throttled Test",
        description="100 HTTP devices across 10 tenants with Poisson messaging and registration throttling.",
        tenants=10,
        devices=100,
        protocols=["http"],
        message_interval=10.0, # Default base interval, Poisson will vary this
        duration_hint="Depends on test length, e.g., 15-30 minutes for observation",
        intensity=TestIntensity.CUSTOM, # Using a new or existing appropriate intensity
        recommended_hardware="8+ CPU cores, 16GB RAM (adjust based on actual load)",
        notes="Custom test: HTTP, Poisson, Throttling (0.2s base delay, 0.3s jitter). Generates reports, graphs, and logs.",
        expected_rps="~10-50 req/sec (highly variable due to Poisson)", # Estimate
        memory_usage="< 2 GB", # Estimate
        # Specific settings for this mode that might be used by stress.py if it checks mode attributes:
        enable_poisson=True,
        enable_throttling=True,
        throttling_base_delay=0.2,
        throttling_jitter=0.3,
        generate_report=True, # Implies --report
    )
}

# Quick reference mapping with more options
QUICK_MODES = {
    "1": "smoke",
    "2": "dev", 
    "5": "quick",
    "10": "light",
    "15": "small",
    "25": "standard",
    "40": "business",
    "50": "medium",
    "65": "enterprise",
    "75": "heavy",
    "100": "stress",
    "150": "extreme",
    "burst": "burst",
    "oneday": "oneday",
    "24h": "oneday",
    "12h": "halfday",
    "48h": "weekend",
    "mqtt": "mqtt_only",
    "http": "http_only"
}


def get_mode_by_devices(device_count: int) -> str:
    """Get the most appropriate mode based on device count."""
    if device_count <= 1:
        return "smoke"
    elif device_count <= 2:
        return "dev"
    elif device_count <= 5:
        return "quick"
    elif device_count <= 10:
        return "light"
    elif device_count <= 15:
        return "small"
    elif device_count <= 25:
        return "standard"
    elif device_count <= 40:
        return "business"
    elif device_count <= 50:
        return "medium"
    elif device_count <= 65:
        return "enterprise"
    elif device_count <= 75:
        return "heavy"
    elif device_count <= 100:
        return "stress"
    else:
        return "extreme"


def list_all_modes() -> None:
    """Print a comprehensive list of all available test modes."""
    print("\n" + "="*100)
    print("🧪 HONO LOAD TEST SUITE - COMPREHENSIVE TEST MODES")
    print("="*100)
    
    # Group modes by intensity
    intensity_groups = {}
    for mode_key, mode in TEST_MODES.items():
        if mode.intensity not in intensity_groups:
            intensity_groups[mode.intensity] = []
        intensity_groups[mode.intensity].append((mode_key, mode))
    
    intensity_order = [
        TestIntensity.MINIMAL,
        TestIntensity.LIGHT,
        TestIntensity.MODERATE,
        TestIntensity.HEAVY,
        TestIntensity.STRESS,
        TestIntensity.EXTREME,
        TestIntensity.ENDURANCE
    ]
    
    intensity_emoji = {
        TestIntensity.MINIMAL: "🟢",
        TestIntensity.LIGHT: "🟡", 
        TestIntensity.MODERATE: "🟠",
        TestIntensity.HEAVY: "🔴",
        TestIntensity.STRESS: "🚨",
        TestIntensity.EXTREME: "💀",
        TestIntensity.ENDURANCE: "⏰"
    }
    
    for intensity in intensity_order:
        if intensity in intensity_groups:
            print(f"\n{intensity_emoji[intensity]} {intensity.value.upper()} INTENSITY TESTS:")
            print("-" * 80)
            
            for mode_key, mode in sorted(intensity_groups[intensity], key=lambda x: x[1].devices):
                print(f"\n  📋 {mode.name.upper()} ({mode_key})")
                print(f"     Description: {mode.description}")
                print(f"     Scale: {mode.tenants} tenants, {mode.devices} devices")
                print(f"     Protocols: {', '.join(mode.protocols)}")
                print(f"     Message interval: {mode.message_interval}s")
                print(f"     Expected RPS: {mode.expected_rps}")
                print(f"     Duration: {mode.duration_hint}")
                print(f"     Memory usage: {mode.memory_usage}")
                print(f"     Hardware: {mode.recommended_hardware}")
                if mode.target_duration_hours > 0:
                    print(f"     Target duration: {mode.target_duration_hours} hours")
                print(f"     Notes: {mode.notes}")
    
    print("\n" + "="*100)
    print("💡 USAGE EXAMPLES:")
    print("   # Quick tests")
    print("   python stress.py --test-mode smoke")
    print("   python stress.py --test-mode 10        # 10 devices")
    print("   python stress.py --test-mode 100       # 100 devices")
    print("")
    print("   # Protocol specific")
    print("   python stress.py --test-mode mqtt      # MQTT only")
    print("   python stress.py --test-mode http      # HTTP only")
    print("")
    print("   # Endurance tests")
    print("   python stress.py --test-mode oneday    # 24-hour test")
    print("   python stress.py --test-mode 24h       # Same as oneday")
    print("   python stress.py --test-mode 12h       # 12-hour test")
    print("")
    print("   # With options")
    print("   python stress.py --test-mode standard --protocols mqtt --report")
    print("   python stress.py --test-mode heavy --interval 2.0 --enhanced-stats")
    print("   python stress.py --list-modes          # Show this help")
    print("="*100)


def get_mode_config(mode_name: str) -> TestMode:
    """Get configuration for a specific test mode."""
    if mode_name in TEST_MODES:
        return TEST_MODES[mode_name]
    elif mode_name in QUICK_MODES:
        return TEST_MODES[QUICK_MODES[mode_name]]
    else:
        available_modes = list(TEST_MODES.keys()) + list(QUICK_MODES.keys())
        raise ValueError(f"Unknown test mode: {mode_name}. Available modes: {available_modes}")


def get_intensity_color(intensity: TestIntensity) -> str:
    """Get color code for intensity level."""
    colors = {
        TestIntensity.MINIMAL: "🟢",
        TestIntensity.LIGHT: "🟡",
        TestIntensity.MODERATE: "🟠", 
        TestIntensity.HEAVY: "🔴",
        TestIntensity.STRESS: "🚨",
        TestIntensity.EXTREME: "💀",
        TestIntensity.ENDURANCE: "⏰"
    }
    return colors.get(intensity, "❓")


def validate_system_requirements(mode: TestMode) -> Dict[str, bool]:
    """Validate if current system meets the requirements for a test mode."""
    import psutil
    import os
    
    # Get system info
    cpu_count = psutil.cpu_count()
    memory_gb = psutil.virtual_memory().total / (1024**3)
    
    # Define minimum requirements per intensity
    requirements = {
        TestIntensity.MINIMAL: {"cpu": 1, "memory": 1},
        TestIntensity.LIGHT: {"cpu": 2, "memory": 4},
        TestIntensity.MODERATE: {"cpu": 4, "memory": 8},
        TestIntensity.HEAVY: {"cpu": 8, "memory": 16},
        TestIntensity.STRESS: {"cpu": 16, "memory": 32},
        TestIntensity.EXTREME: {"cpu": 24, "memory": 64},
        TestIntensity.ENDURANCE: {"cpu": 16, "memory": 32}  # Endurance needs stability over performance
    }
    
    min_req = requirements.get(mode.intensity, {"cpu": 1, "memory": 1})
    
    validation = {
        "cpu_ok": cpu_count >= min_req["cpu"],
        "memory_ok": memory_gb >= min_req["memory"],
        "cpu_count": cpu_count,
        "memory_gb": memory_gb,
        "min_cpu": min_req["cpu"],
        "min_memory": min_req["memory"]
    }
    
    # Additional warnings for endurance tests
    if mode.intensity == TestIntensity.ENDURANCE:
        validation["endurance_warning"] = True
        validation["disk_space_gb"] = psutil.disk_usage('.').free / (1024**3)
    
    return validation


def get_endurance_warnings(mode: TestMode) -> List[str]:
    """Get specific warnings for endurance tests."""
    warnings = []
    
    if mode.intensity == TestIntensity.ENDURANCE:
        warnings.extend([
            "⚠️  ENDURANCE TEST WARNINGS:",
            "   • Monitor disk space - logs can grow large over time",
            "   • Ensure stable power supply (UPS recommended)",
            "   • Monitor for memory leaks during long runs",
            "   • Set up log rotation to prevent disk filling",
            "   • Consider running during off-peak hours",
        ])
        
        if mode.target_duration_hours >= 24:
            warnings.extend([
                "   • Plan for potential network interruptions",
                "   • Monitor system temperature and cooling",
                "   • Have monitoring/alerting in place"
            ])
    
    return warnings