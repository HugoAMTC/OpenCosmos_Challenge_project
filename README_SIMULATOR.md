# Flight Operations Procedure Simulator
## OC-FL-OP-PL Rev 1 — Mantis Satellite Contact Automation

A Python-based simulator for the automated execution of satellite flight operations contact procedures. This project implements the complete 7-phase contact sequence for the Open Cosmos Mantis satellite, including realistic spacecraft physics, command/response handling, and comprehensive anomaly injection capabilities.

---

This simulator automates the procedures defined in the document **Open Cosmos - Flight Operational Contact Plan & Procedure - Rev 1.0 - Internal Restricted**. It simulates a complete satellite contact from pre-contact preparation through post-contact actions, including:

- **Phase 0**: Pre-contact Preparation (T-30:00 to T-00:01)
- **Phase 1**: Contact Acquisition (T+00:00 to T+01:15)
- **Phase 2**: Housekeeping & Sat Health Check (T+01:15 to T+02:30)
- **Phase 3**: Platform Data Download (T+02:30 to T+03:10)
- **Phase 4**: Payload Data Download (T+03:10 to T+06:55)
- **Phase 5**: COMMS Configuration Change (T+07:00 to T+07:50)
- **Phase 6**: Pre-LOS Close-out (T+08:30 to T+09:30)
- **Phase 7**: Post-contact Actions (within 30 min of LOS)


### Module Structure ###


#### **config.py** — Mission Configuration & Constants
Single source of truth for all mission parameters.
- Timing constants (phase boundaries, step offsets)
- COMMS parameters (link rates, timeouts)
- Operational limits (Yellow/Red thresholds)
- Initial satellite state
- Anomaly presets
- Command definitions
- Physics parameters


#### **satellite.py** — Mantis Spacecraft Model
Simulates the Open Cosmos Mantis satellite with realistic physics:
- **EPS Subsystem**: Battery charging/discharging, power draw
- **OBC Subsystem**: Temperature, storage utilization, uptime
- **COMMS Subsystem**: TX/RX state, config versions, RSSI, TM lock
- **ADCS Subsystem**: Attitude mode, pointing error, wheel RPM
- **Thermal Subsystem**: Multi-point temperature modeling with passive cooling
- **Physics Engine**: Updates power consumption, thermal effects, data transfer progress per simulated second

**Command Interface:**
- All commands return realistic ACK/NACK responses
- COMMS restart with TM loss/restoration (~30 sec)
- File transfer simulation (checksums, progress tracking)
- Anomaly injection support (battery drain, thermal spike, restart failure, etc.)


#### **flight_contact_plan.py** — Flight Operations Procedure
Implements all 7 contact phases with complete OC-FL-OP-PL Rev 1 compliance:
- Each step has defined expected vs. actual results
- Pass/Fail/Deferred status tracking
- Precondition verification before critical operations (e.g., COMMS config change)
- Anomaly detection and logging
- Deferral logic for optional phases
- Comprehensive ops log with timestamped entries

**Key Classes:**
- `FlightOperationsProcedure`: Main orchestrator
- `StepResult`: Tracks pass/fail for each procedure step
- `OpsLog`: Captures all anomalies, entries, and deferred actions


#### **main.py** — CLI Runner
Command-line interface with flexible options:

```bash
python main.py                              # Run standard pass
python main.py --anomaly low_battery        # Inject anomaly
python main.py --speed 10                   # Run 10x real-time
python main.py --save report.json           # Save JSON report
python main.py --telemetry telemetry.json   # Save telemetry snapshots
```

---


### Prerequisites
- Python 3.8 or later

### Installation
1. Clone or download the Flight_Operations folder
2. Navigate to the directory:
   ```bash
   cd "d:\Profissional\Jobs\Open Cosmos\Satellite Flight Operator\Satellite Operations Challenge\Code\Flight_Operations"
   ```

### Running a Standard Pass
```bash
python main.py
```

**Output:**
- Detailed step-by-step execution log
- Pass summary (phases, phases completed, data downloads)
- Final spacecraft state (battery, temperature, storage, config version)

### Running with Anomalies

#### Available Anomaly Presets (see config.py):
- `none` — No anomalies (default)
- `low_battery` — Battery SoC drops to 38% (below Yellow limit of 45%)
- `high_obc_temp` — OBC temperature rises to 58°C (Yellow limit)
- `high_storage` — Storage utilization at 88% (above 85% Yellow)
- `tm_lock_fail` — TM lock fails to establish (Phase 1 critical failure)
- `comms_restart_fail` — COMMS restart command fails
- `safe_mode_entry` — Spacecraft enters SAFE mode (contact halts)
- `payload_download_thermal` — OBC temp at 59°C during payload DL (triggers mid-transfer pause)

#### Examples:
```bash
# Low battery scenario
python main.py --anomaly low_battery

# COMMS restart failure
python main.py --anomaly comms_restart_fail

# Thermal constraint during payload download
python main.py --anomaly payload_download_thermal
```

### Saving Reports

```bash
# Save detailed JSON report
python main.py --save pass_report.json

# Save telemetry snapshots (battery, temp, RSSI, etc.)
python main.py --telemetry telemetry.json

# Save both + 5x simulation speed
python main.py --speed 5 --save report.json --telemetry tel.json
```

**Report includes:**
- Detailed step results (expected vs. actual)
- All parameter checks and checksums
- Anomalies detected with timestamps
- Deferred items with reasons
- Telemetry snapshots every 30 sim seconds
- Ops log entries

---

## Examples & Scenarios

### Scenario 1: Nominal Pass
```bash
python main.py --save nominal_pass.json
```
Expected: All phases complete, all data downloaded, COMMS config changed.

### Scenario 2: Battery Constraint
```bash
python main.py --anomaly low_battery --save low_battery_pass.json
```
Expected: Phase 2 flags low battery. Phase 5 (config change) may defer due to preconditions.

### Scenario 3: Thermal Constraint During Payload Download
```bash
python main.py --anomaly payload_download_thermal --save thermal_scenario.json
```
Expected: Phase 4 mid-transfer check detects high temp, pause/resume logic may trigger.

### Scenario 4: COMMS Restart Failure
```bash
python main.py --anomaly comms_restart_fail --save comms_fail.json
```
Expected: Phase 5 config change fails (NACK). Contact continues but defer to next pass.

### Scenario 5: TM Lock Failure (Critical)
```bash
python main.py --anomaly tm_lock_fail --save critical_failure.json
```
Expected: Phase 1 fails immediately (CRITICAL). Procedure halts. Contact aborted.

---

## Output & Diagnostics

### Console Output
- **Real-time logging** of each procedure step
- **Anomaly alerts** (WARNING/ERROR) for out-of-limit conditions
- **Phase transitions** marked with banners
- **Final summary** with pass/fail statistics

### JSON Report Structure
```json
{
  "metadata": {...},
  "pass_summary": {
    "aos_time": 0.0,
    "los_time": 570.0,
    "duration_seconds": 570,
    "critical_failed": false
  },
  "step_results": [
    {
      "step_id": "1.1",
      "phase": "PHASE_1",
      "status": "PASS",
      "expected": "...",
      "actual": "...",
      "checks": {...}
    },
    ...
  ],
  "phases_completed": {
    "PHASE_0": true,
    "PHASE_1": true,
    ...
  },
  "data_downloads": {
    "platform": true,
    "payload": true,
    "config_change": true
  },
  "anomalies": 2,
  "deferred_items": 1,
  "ops_log_entries": [...],
  "anomalies": [...]
}
```

### Telemetry Log
```json
[
  {
    "simulation_time": 0.0,
    "battery_soc": 72.0,
    "obc_temperature": 28.0,
    "rssi": -92.0,
    "storage_utilization": 62.0,
    "tx_enabled": false,
    "frame_sync": "RED"
  },
  ...
]
```
---

## References

- **OC-FL-OP-PL Rev 1**: Flight Operational Contact Plan & Procedure - Rev 1 Document

---

## Version History

- **v1.0** (2025-04-16): Initial release
  - Complete 7-phase procedure implementation
  - Mantis spacecraft model with physics
  - 8 anomaly presets
  - CLI with JSON reporting

---

## Support

For questions or issues, refer to: Hugo Carvalho

**Happy flying! 🛰️**
