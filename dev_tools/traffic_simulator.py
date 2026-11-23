"""
CLI runner for traffic simulator dev tool.
Usage:
    python -m dev_tools.traffic_simulator
"""
from dev_tools.traffic_simulator_service import TrafficSimulatorService

if __name__ == "__main__":
    import sys
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    orders = TrafficSimulatorService.pulse(count=count)
    print(f"Generated {len(orders)} simulated orders.")
