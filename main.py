
"""
Flight Operations Automation CLI
FLIGHT-OPERATIONS-CONTACT-PLAN Rev 1.0 Procedure Simulator

Usage Example:
    python main.py                          # Run standard pass
    python main.py --anomaly low_battery    # Inject anomaly
    python main.py --speed 10               # Run 10x real-time
    python main.py --save report.json       # Save results to JSON
    python main.py --help                   # Show help


Autor: Hugo Carvalho

Open Cosmos Project Interview - Satellite Flight Operator Challenge


"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from config import ANOMALY_PRESETS, INITIAL_SATELLITE_STATE, Phase
from satellite import MantisSpacecraft
from flight_contact_plan import FlightOperationsProcedure, OpsLog


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Flight Operations Procedure Simulator - OC-MOP-FO-001 Rev 2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standard pass execution
  python main.py

  # Inject low battery anomaly (check config for available anomalies)
  python main.py --anomaly low_battery

  # Run 5x real-time speed
  python main.py --speed 5

  # Save detailed report to JSON
  python main.py --save report.json

  # Combine options
  python main.py --anomaly high_obc_temp --speed 2 --save results.json
        """
    )
    
    parser.add_argument(
        "--anomaly",
        type=str,
        default="none",
        choices=list(ANOMALY_PRESETS.keys()),
        help="Inject named anomaly preset (default: none)"
    )
    
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Simulation speed multiplier (default: 1.0 = real-time)"
    )
    
    parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Save detailed report to JSON file"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level)"
    )
    
    parser.add_argument(
        "--telemetry",
        type=str,
        default=None,
        help="Save telemetry snapshots to JSON file"
    )
    
    return parser.parse_args()


def print_banner():
    """Print welcome banner."""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║     MANTIS SATELLITE FLIGHT OPERATIONS PROCEDURE SIMULATOR    ║
║              FLIGHT-OPERATIONS-CONTACT-PLAN Rev 1.0           ║
║         Open Cosmos Project Interview - HUGO CARVALHO         ║
╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def simulate_pass(args: Any) -> tuple[FlightOperationsProcedure, list]:
    """
    Run full pass simulation.
    
    Args:
        args: Parsed command-line arguments
    
    Returns:
        Tuple of (procedure, telemetry_log)
    """
    print(f"\n[SIMULATOR] Initializing spacecraft...")
    
    # Get anomaly preset
    anomaly = ANOMALY_PRESETS.get(args.anomaly, {})
    if args.anomaly != "none":
        print(f"[SIMULATOR] Anomaly preset: {args.anomaly}")
        print(f"              Parameters: {anomaly}")
    
    # Create spacecraft
    spacecraft = MantisSpacecraft(anomaly=anomaly)
    
    # Create procedure
    procedure = FlightOperationsProcedure(spacecraft)
    
    print(f"[SIMULATOR] Simulation initialized")
    print(f"[SIMULATOR] Initial battery SoC: {spacecraft.get_battery_soc():.1f}%")
    print(f"[SIMULATOR] Initial OBC temp: {spacecraft.get_obc_temperature():.1f}°C")
    print(f"[SIMULATOR] Initial storage: {spacecraft.get_storage_utilization():.1f}%")
    
    print(f"\n[SIMULATOR] Starting Flight Plan Execution...")
    print(f"[SIMULATOR] Real-time speed: {args.speed}x\n")
    
    # Simulate satellite operations over time
    # Phase 0 runs before contact (T-30:00 to T-00:01)
    # Then we jump to T+00:00 (AOS) for Phase 1
    telemetry_snapshots = []
    
    # Pre-contact phase
    print("─" * 70)
    procedure.execute_phase_0()
    
    print("─" * 70)
    print("[SIMULATOR] Awaiting AOS (T+00:00)...")
    print("─" * 70 + "\n")
    
    # Simulate from AOS (T+00:00) through LOS (T+09:30)
    simulation_time = 0.0  # Start at T+00:00 (AOS)
    end_time = 570.0  # T+09:30 (LOS)
    dt = 1.0  # 1-second timestep
    
    # Adjust timestep for speed
    if args.speed > 1.0:
        # For display purposes, still use 1s logical steps
        # but advance faster
        pass
    
    contact_started = False
    phase_boundaries = {
        Phase.PHASE_1: (0, 75),
        Phase.PHASE_2: (75, 150),
        Phase.PHASE_3: (150, 190),
        Phase.PHASE_4: (190, 415),
        Phase.PHASE_5: (420, 470),
        Phase.PHASE_6: (510, 570),
    }
    
    while simulation_time <= end_time:
        # Update spacecraft physics
        spacecraft.update(dt)
        
        # Execute procedures at appropriate times
        if simulation_time == 0.0 and not contact_started:
            contact_started = True
            procedure.execute_phase_1()
            print()
        elif 75.0 <= simulation_time < 150.0 and not procedure.phases_completed[Phase.PHASE_2]:
            procedure.execute_phase_2()
            print()
        elif 150.0 <= simulation_time < 190.0 and not procedure.phases_completed[Phase.PHASE_3]:
            procedure.execute_phase_3()
            print()
        elif 190.0 <= simulation_time < 415.0 and not procedure.phases_completed[Phase.PHASE_4]:
            procedure.execute_phase_4()
            print()
        elif 420.0 <= simulation_time < 470.0 and not procedure.phases_completed[Phase.PHASE_5]:
            procedure.execute_phase_5()
            print()
        elif 510.0 <= simulation_time < 570.0 and not procedure.phases_completed[Phase.PHASE_6]:
            procedure.execute_phase_6()
            print()
        
        # Capture telemetry snapshot every 30 seconds
        if int(simulation_time) % 30 == 0:
            frame = spacecraft.generate_telemetry_frame()
            telemetry_snapshots.append({
                "simulation_time": simulation_time,
                "battery_soc": frame.battery_soc,
                "obc_temperature": frame.obc_temperature,
                "rssi": frame.rssi,
                "storage_utilization": frame.obc_storage_utilization,
                "tx_enabled": frame.tx_enabled,
                "frame_sync": frame.frame_sync,
            })
        
        simulation_time += dt
    
    # End of contact
    print("─" * 70)
    procedure.execute_phase_7()
    print("─" * 70 + "\n")
    
    return procedure, telemetry_snapshots


def print_summary(procedure: FlightOperationsProcedure, telemetry: list):
    """Print pass execution summary."""
    report = procedure.generate_report()
    
    print("\n╔═══════════════════════════════════════════════════════════════╗")
    print("║                     PASS EXECUTION SUMMARY                    ║")
    print("╚═══════════════════════════════════════════════════════════════╝\n")
    
    # Pass overview
    summary = report["pass_summary"]
    print(f"Status:              {'✘ CRITICAL FAILURE' if summary['critical_failed'] else '✓ NOMINAL'}")
    print(f"Duration:            {summary['duration_seconds']:.0f} seconds ({summary['duration_seconds']/60:.1f} min)")
    
    # Steps summary
    steps = report["step_results"]
    print(f"\nSteps Executed:      {steps['total']}")
    print(f"  Passed:            {steps['passed']}")
    print(f"  Failed:            {steps['failed']}")
    print(f"  Deferred:          {steps['deferred']}")
    
    # Phases summary
    print(f"\nPhases Completed:")
    for phase_name, completed in report["phases_completed"].items():
        status = "✓" if completed else "✗"
        print(f"  {status} {phase_name}")
    
    # Data downloads
    dl = report["data_downloads"]
    print(f"\nData Downloads:")
    print(f"  Platform Log:      {'✓' if dl['platform'] else '✗'}")
    print(f"  Payload Data:      {'✓' if dl['payload'] else '✗'}")
    print(f"  COMMS Config:      {'✓' if dl['config_change'] else '⊘ DEFERRED'}")
    
    # Anomalies
    print(f"\nAnomalies Detected:  {report['anomalies']}")
    if report['anomalies'] > 0:
        for anom in procedure.ops_log.anomalies:
            print(f"  • {anom['parameter']}: {anom['value']} ({anom['limit']})")
    
    # Final spacecraft state
    frame = procedure.spacecraft.generate_telemetry_frame()
    print(f"\nFinal Spacecraft State:")
    print(f"  Battery SoC:       {frame.battery_soc:.1f}%")
    print(f"  OBC Temperature:   {frame.obc_temperature:.1f}°C")
    print(f"  OBC Storage:       {frame.obc_storage_utilization:.1f}%")
    print(f"  RSSI:              {frame.rssi:.1f} dBm")
    print(f"  Config Version:    {frame.comms_config_version}")
    
    print("\n")


def save_report(procedure: FlightOperationsProcedure, telemetry: list, filename: str):
    """Save detailed report to JSON."""
    report = procedure.generate_report()
    
    # Add step-by-step results
    step_results = []
    for step in procedure.step_results:
        step_results.append({
            "step_id": step.step_id,
            "phase": step.phase.name,
            "time_offset": step.time_offset,
            "status": step.status,
            "expected": step.expected_result,
            "actual": step.actual_result,
            "error": step.error_msg,
            "checks": step.parameter_checks,
        })
    
    # Build report
    full_report = {
        "metadata": {
            "simulation_date": datetime.now().isoformat(),
            "procedure": "OC-MOP-FO-001 Rev 2",
            "simulator_version": "1.0",
        },
        "pass_summary": report["pass_summary"],
        "step_results": step_results,
        "phases_completed": report["phases_completed"],
        "data_downloads": report["data_downloads"],
        "telemetry_snapshots": telemetry,
        "ops_log_entries": procedure.ops_log.entries,
        "anomalies": procedure.ops_log.anomalies,
        "deferred_items": procedure.ops_log.deferred_items,
    }
    
    # Write to file
    with open(filename, 'w') as f:
        json.dump(full_report, f, indent=2)
    
    print(f"[SAVED] Detailed report: {filename}")


def save_telemetry(telemetry: list, filename: str):
    """Save telemetry log to JSON."""
    with open(filename, 'w') as f:
        json.dump(telemetry, f, indent=2)
    print(f"[SAVED] Telemetry log: {filename}")


def main():
    """Main entry point."""
    args = parse_arguments()
    
    print_banner()
    
    try:
        # Run simulation
        procedure, telemetry = simulate_pass(args)
        
        # Print summary
        print_summary(procedure, telemetry)
        
        # Save reports if requested
        if args.save:
            save_report(procedure, telemetry, args.save)
        
        if args.telemetry:
            save_telemetry(telemetry, args.telemetry)
        
        # Return exit code based on critical failure
        return 1 if procedure.critical_failed else 0
        
    except Exception as e:
        print(f"\n✘ SIMULATOR ERROR: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
