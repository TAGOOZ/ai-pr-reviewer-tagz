#!/usr/bin/env python3
"""Quick test script for the dashboard."""

import sys
import os

# Add the python directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

from coderabbit_ai.dashboard import (
    get_system_metrics,
    get_component_status,
    get_environment_variables
)

def test_system_metrics():
    """Test system metrics collection."""
    print("=" * 80)
    print("SYSTEM METRICS")
    print("=" * 80)
    metrics = get_system_metrics()

    if metrics:
        print(f"✅ CPU: {metrics['cpu']['usage_percent']}% ({metrics['cpu']['count']} cores)")
        print(f"✅ Memory: {metrics['memory']['used_gb']}/{metrics['memory']['total_gb']} GB ({metrics['memory']['percent']}%)")
        print(f"✅ Disk: {metrics['disk']['used_gb']}/{metrics['disk']['total_gb']} GB ({metrics['disk']['percent']}%)")
    else:
        print("❌ Failed to get system metrics")
    print()

def test_component_status():
    """Test component status checks."""
    print("=" * 80)
    print("COMPONENT STATUS")
    print("=" * 80)
    components = get_component_status()

    for name, info in components.items():
        status_icon = {
            'ok': '✅',
            'warning': '⚠️',
            'error': '❌'
        }.get(info['status'], '❓')

        message = info.get('message', info.get('version', ''))
        print(f"{status_icon} {name:25s} [{info['status']:8s}] {message}")
    print()

def test_environment_variables():
    """Test environment variables retrieval."""
    print("=" * 80)
    print("ENVIRONMENT VARIABLES")
    print("=" * 80)
    env_vars = get_environment_variables()

    for name, info in env_vars.items():
        value = info['value']
        masked = " (masked)" if info['masked'] else ""
        if value is None:
            print(f"⚪ {name:35s} = <not set>")
        else:
            print(f"✅ {name:35s} = {value}{masked}")
    print()

if __name__ == "__main__":
    print("\n🚀 Testing CodeRabbit AI Dashboard Components\n")

    test_system_metrics()
    test_component_status()
    test_environment_variables()

    print("=" * 80)
    print("✅ Dashboard component tests complete!")
    print("=" * 80)
    print("\nTo start the server with dashboard:")
    print("  python -m coderabbit_ai.server")
    print("\nThen visit:")
    print("  http://localhost:8000/dashboard")
    print()
