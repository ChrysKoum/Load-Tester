"""
Utilities and constants for Hono Load Test Suite.
Contains library availability checks and common constants.
"""

# Try to import reporting libraries
try:
    import matplotlib.pyplot as plt
    import pandas as pd
    REPORTING_AVAILABLE = True
except ImportError:
    REPORTING_AVAILABLE = False

# Try to import additional protocol libraries
try:
    import coap
    COAP_AVAILABLE = True
except ImportError:
    COAP_AVAILABLE = False

try:
    import amqp
    AMQP_AVAILABLE = True
except ImportError:
    AMQP_AVAILABLE = False


def get_library_status():
    """Return a dictionary of library availability status."""
    return {
        'reporting': REPORTING_AVAILABLE,
        'coap': COAP_AVAILABLE,
        'amqp': AMQP_AVAILABLE
    }
